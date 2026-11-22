"""Document Readiness Lifecycle (`document-status.v1`) types, errors, and wait loops.

All public TypedDict and signature annotations use ``Optional``/``Union``
(never PEP 604 ``X | None``) so ``typing.get_type_hints()`` works on Python 3.9.
"""

from __future__ import annotations

import asyncio
import datetime
import email.utils
import math
import threading
import time
from typing import Any, Awaitable, Callable, Literal, Optional, Tuple, TypedDict, Union

import httpx

from ._errors import MindGraphError
from ._retry import TERMINAL_CODES

DOCUMENT_STATUS_CONTRACT = "document-status.v1"
DEFAULT_WAIT_TIMEOUT_MS = 60_000
MIN_WAIT_TIMEOUT_MS = 1
MAX_WAIT_TIMEOUT_MS = 300_000
DEFAULT_WAIT_INTERVAL_MS = 1_000
MIN_WAIT_INTERVAL_MS = 100

ReadinessDimension = Literal["lexical", "vector", "extraction"]
DimensionState = Literal["ready", "not_ready", "unknown", "not_requested"]
AttemptState = Literal[
    "running",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "cancelled_by_deletion",
    "interrupted",
    "failed_abandoned",
]

VALID_DIMENSIONS = frozenset(("lexical", "vector", "extraction"))
VALID_DIMENSION_STATES = frozenset(("ready", "not_ready", "unknown", "not_requested"))


class DocumentStatusReadiness(TypedDict):
    lexical: DimensionState
    vector: DimensionState
    extraction: DimensionState


class DocumentStatusError(TypedDict):
    code: str
    message: str
    retriable: bool


class DocumentStatus(TypedDict):
    contract: Literal["document-status.v1"]
    document_uid: str
    document_version: int
    generation_id: Optional[str]
    attempt_id: Optional[str]
    job_id: Optional[str]
    job_available: bool
    processing_status: str
    attempt_state: Optional[AttemptState]
    content_revision: Optional[str]
    pipeline_digest: Optional[str]
    readiness: DocumentStatusReadiness
    observed_at: str
    error: Optional[DocumentStatusError]


class ValidationError(MindGraphError, ValueError):
    """Raised immediately before issuing any HTTP request on invalid parameters."""

    def __init__(self, message: str):
        MindGraphError.__init__(
            self,
            message,
            0,
            {"code": "validation_error", "retriable": False},
        )


class ReadinessUnknownError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        last_status: DocumentStatus,
        message: Optional[str] = None,
    ):
        super().__init__(
            message or f"Readiness is unknown for document {document_uid}",
            200,
            {"code": "readiness_unknown", "retriable": False},
        )
        self.document_uid = document_uid
        self.last_status = last_status


class DocumentSupersededError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        expected_attempt_id: str,
        observed_attempt_id: str,
        last_status: DocumentStatus,
    ):
        super().__init__(
            f"Document {document_uid} attempt {expected_attempt_id} was superseded by {observed_attempt_id}",
            200,
            {"code": "document_superseded", "retriable": False},
        )
        self.document_uid = document_uid
        self.expected_attempt_id = expected_attempt_id
        self.observed_attempt_id = observed_attempt_id
        self.last_status = last_status


class ReadinessNotRequestedError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        dimension: ReadinessDimension,
        last_status: DocumentStatus,
    ):
        super().__init__(
            f"Readiness dimension {dimension!r} was not requested for document {document_uid}",
            200,
            {"code": "readiness_not_requested", "retriable": False},
        )
        self.document_uid = document_uid
        self.dimension = dimension
        self.last_status = last_status


class DocumentIncompleteError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        dimension: ReadinessDimension,
        last_status: DocumentStatus,
    ):
        super().__init__(
            f"Document {document_uid} ended in state {last_status.get('attempt_state')!r} without {dimension!r} readiness",
            200,
            {"code": "document_incomplete", "retriable": False},
        )
        self.document_uid = document_uid
        self.dimension = dimension
        self.last_status = last_status


class DocumentWaitTimeoutError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        attempt_id: Optional[str],
        last_status: Optional[DocumentStatus],
        message: Optional[str] = None,
    ):
        super().__init__(
            message or f"Timed out waiting for document {document_uid}",
            0,
            {"code": "document_wait_timeout", "retriable": True},
        )
        self.document_uid = document_uid
        self.attempt_id = attempt_id
        self.last_status = last_status


class DocumentWaitCancelledError(MindGraphError):
    def __init__(
        self,
        document_uid: str,
        attempt_id: Optional[str],
        last_status: Optional[DocumentStatus],
    ):
        super().__init__(
            f"Cancelled waiting for document {document_uid}",
            0,
            {"code": "document_wait_cancelled", "retriable": False},
        )
        self.document_uid = document_uid
        self.attempt_id = attempt_id
        self.last_status = last_status


def validate_wait_params(
    *,
    attempt_id: Optional[str],
    until: str,
    timeout_ms: int,
    interval_ms: int,
) -> Tuple[Optional[str], ReadinessDimension, int, int]:
    if (
        isinstance(timeout_ms, bool)
        or not isinstance(timeout_ms, int)
        or timeout_ms < MIN_WAIT_TIMEOUT_MS
        or timeout_ms > MAX_WAIT_TIMEOUT_MS
    ):
        raise ValidationError(
            f"timeout_ms must be a finite integer in [{MIN_WAIT_TIMEOUT_MS}, {MAX_WAIT_TIMEOUT_MS}]"
        )
    if not isinstance(until, str) or until not in VALID_DIMENSIONS:
        raise ValidationError(
            "until must be one of 'lexical', 'vector', or 'extraction'"
        )
    if (
        isinstance(interval_ms, bool)
        or not isinstance(interval_ms, (int, float))
        or not math.isfinite(interval_ms)
    ):
        raise ValidationError("interval_ms must be a finite number")
    clamped_interval = max(MIN_WAIT_INTERVAL_MS, int(interval_ms))
    if attempt_id is not None:
        if not isinstance(attempt_id, str) or len(attempt_id) == 0:
            raise ValidationError("attempt_id must be a non-empty string when provided")
    return attempt_id, until, timeout_ms, clamped_interval  # type: ignore[return-value]


def parse_retry_after_ms(
    header: Optional[str],
    now_epoch_ms: Optional[float] = None,
) -> Optional[int]:
    """Parse RFC 9110 Retry-After (ASCII integer seconds or HTTP-date) into ms."""
    if not header:
        return None
    trimmed = header.strip()
    if not trimmed:
        return None
    if trimmed.isascii() and trimmed.isdigit():
        return int(trimmed) * 1000
    try:
        dt = email.utils.parsedate_to_datetime(trimmed)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    now_ms = time.time() * 1000.0 if now_epoch_ms is None else now_epoch_ms
    delta_ms = dt.timestamp() * 1000.0 - now_ms
    return max(0, int(math.ceil(delta_ms)))


def validate_document_status_payload(
    value: Any,
    http_status: int = 200,
) -> DocumentStatus:
    if not isinstance(value, dict):
        raise MindGraphError(
            "Incompatible document status response",
            http_status,
            {"code": "incompatible_response", "retriable": False},
        )
    readiness = value.get("readiness")
    valid_readiness = (
        isinstance(readiness, dict)
        and readiness.get("lexical") in VALID_DIMENSION_STATES
        and readiness.get("vector") in VALID_DIMENSION_STATES
        and readiness.get("extraction") in VALID_DIMENSION_STATES
    )
    has_valid_attempt_id = "attempt_id" in value and (
        value["attempt_id"] is None or isinstance(value["attempt_id"], str)
    )
    has_valid_attempt_state = "attempt_state" in value and (
        value["attempt_state"] is None or isinstance(value["attempt_state"], str)
    )
    if (
        value.get("contract") != DOCUMENT_STATUS_CONTRACT
        or not isinstance(value.get("document_uid"), str)
        or not has_valid_attempt_id
        or not has_valid_attempt_state
        or not valid_readiness
    ):
        raise MindGraphError(
            "Incompatible document status response",
            http_status,
            {"code": "incompatible_response", "retriable": False},
        )
    return value  # type: ignore[return-value]


def _parse_response_body(resp: httpx.Response) -> Any:
    if not resp.content:
        return None
    try:
        return resp.json()
    except Exception:
        return resp.text


def _permits_503_retry(body: Any) -> bool:
    if not isinstance(body, dict):
        return True
    if body.get("retriable") is False:
        return False
    code = body.get("code")
    if isinstance(code, str) and code in TERMINAL_CODES:
        return False
    return True


def _evaluate_200_status(
    document_uid: str,
    until: ReadinessDimension,
    pinned_attempt_id: Optional[str],
    status: DocumentStatus,
) -> Tuple[bool, str]:
    """Evaluate a validated 200 DocumentStatus.

    Returns ``(is_ready, updated_pinned_attempt_id)`` or raises the exact
    §5.2 typed exception on legacy/superseded/not_requested/terminal states.
    """
    observed_attempt = status.get("attempt_id")
    if observed_attempt is None:
        raise ReadinessUnknownError(
            document_uid,
            status,
            f"Document {document_uid} is not lifecycle-tracked (attempt_id is null)",
        )
    if pinned_attempt_id is None:
        pinned_attempt_id = observed_attempt
    elif observed_attempt != pinned_attempt_id:
        raise DocumentSupersededError(
            document_uid,
            pinned_attempt_id,
            observed_attempt,
            status,
        )

    dim_state = status["readiness"][until]
    if dim_state == "ready":
        return True, pinned_attempt_id
    if dim_state == "not_requested":
        raise ReadinessNotRequestedError(document_uid, until, status)

    # Classify active vs terminal strictly by attempt_state (never processing_status).
    if status.get("attempt_state") != "running":
        if dim_state == "unknown":
            raise ReadinessUnknownError(document_uid, status)
        raise DocumentIncompleteError(document_uid, until, status)

    return False, pinned_attempt_id


def _is_cancelled(cancel_event: Union[threading.Event, asyncio.Event, None]) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _compute_backoff_ms(
    retry_after_header: Optional[str],
    interval_ms: int,
    remaining_ms: float,
    now_epoch_ms: Optional[float],
) -> Optional[float]:
    """Return sleep duration in ms, or ``None`` if Retry-After exceeds deadline."""
    retry_after_ms = parse_retry_after_ms(retry_after_header, now_epoch_ms)
    if retry_after_ms is not None and retry_after_ms >= remaining_ms:
        return None
    desired = max(float(interval_ms), float(retry_after_ms or 0))
    return min(desired, remaining_ms)


async def _wait_for_cancel_event(
    cancel_event: Union[asyncio.Event, threading.Event],
) -> None:
    if isinstance(cancel_event, asyncio.Event):
        await cancel_event.wait()
        return
    while not cancel_event.is_set():
        await asyncio.sleep(0.02)


async def _fetch_cancellable_async(
    fetch_once: Callable[[float], Awaitable[httpx.Response]],
    timeout_s: float,
    cancel_event: Union[asyncio.Event, threading.Event, None],
) -> Tuple[Optional[httpx.Response], bool]:
    """Await ``fetch_once`` while racing against ``cancel_event``.

    Returns ``(response, False)`` on completion or ``(None, True)`` if cancelled
    while the request was in flight.
    """
    if cancel_event is None:
        return await fetch_once(timeout_s), False
    if cancel_event.is_set():
        return None, True

    fetch_task: asyncio.Task[httpx.Response] = asyncio.create_task(
        fetch_once(timeout_s)
    )
    cancel_task: asyncio.Task[None] = asyncio.create_task(
        _wait_for_cancel_event(cancel_event)
    )
    try:
        done, pending = await asyncio.wait(
            {fetch_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if cancel_task in done and cancel_event.is_set():
            if fetch_task in done and not fetch_task.cancelled():
                # Retrieve any exception to avoid "Task exception was never retrieved".
                try:
                    fetch_task.exception()
                except Exception:
                    pass
            return None, True

        return fetch_task.result(), False
    except BaseException:
        for task in (fetch_task, cancel_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(fetch_task, cancel_task, return_exceptions=True)
        raise


def run_wait_for_document_sync(
    *,
    document_uid: str,
    path: str,
    attempt_id: Optional[str],
    until: ReadinessDimension,
    timeout_ms: int,
    interval_ms: int,
    cancel_event: Optional[threading.Event],
    fetch_once: Callable[[float], httpx.Response],
    monotonic_ms: Optional[Callable[[], float]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
    epoch_ms: Optional[Callable[[], float]] = None,
) -> DocumentStatus:
    pinned_attempt_id = attempt_id
    last_status: Optional[DocumentStatus] = None

    if _is_cancelled(cancel_event):
        raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)

    now_mono = monotonic_ms or (lambda: time.monotonic() * 1000.0)
    now_epoch = epoch_ms or (lambda: time.time() * 1000.0)
    deadline = now_mono() + float(timeout_ms)

    def _sleep(delay_ms: float) -> None:
        if sleep_fn is not None:
            sleep_fn(delay_ms)
            return
        if cancel_event is not None:
            cancel_event.wait(delay_ms / 1000.0)
        else:
            time.sleep(delay_ms / 1000.0)

    while True:
        if _is_cancelled(cancel_event):
            raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)
        remaining_ms = deadline - now_mono()
        if remaining_ms <= 0:
            raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)

        try:
            resp = fetch_once(remaining_ms / 1000.0)
        except httpx.TimeoutException as exc:
            if _is_cancelled(cancel_event):
                raise DocumentWaitCancelledError(
                    document_uid, pinned_attempt_id, last_status
                ) from exc
            raise DocumentWaitTimeoutError(
                document_uid, pinned_attempt_id, last_status
            ) from exc

        if _is_cancelled(cancel_event):
            raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)

        body = _parse_response_body(resp)
        if resp.status_code == 200:
            status = validate_document_status_payload(body, 200)
            last_status = status
            ready, pinned_attempt_id = _evaluate_200_status(
                document_uid, until, pinned_attempt_id, status
            )
            if ready:
                return status
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            delay_ms = _compute_backoff_ms(
                resp.headers.get("retry-after"),
                interval_ms,
                remaining_after,
                now_epoch(),
            )
            if delay_ms is None:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            _sleep(delay_ms)
            continue

        code = body.get("code") if isinstance(body, dict) else None
        if resp.status_code == 409 and code == "status_changed":
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            _sleep(min(float(interval_ms), remaining_after))
            continue

        if resp.status_code == 429 or (
            resp.status_code == 503 and _permits_503_retry(body)
        ):
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            delay_ms = _compute_backoff_ms(
                resp.headers.get("retry-after"),
                interval_ms,
                remaining_after,
                now_epoch(),
            )
            if delay_ms is None:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            _sleep(delay_ms)
            continue

        raise MindGraphError(
            f"GET {path} failed: {resp.status_code}",
            resp.status_code,
            body,
        )


async def run_wait_for_document_async(
    *,
    document_uid: str,
    path: str,
    attempt_id: Optional[str],
    until: ReadinessDimension,
    timeout_ms: int,
    interval_ms: int,
    cancel_event: Union[asyncio.Event, threading.Event, None],
    fetch_once: Callable[[float], Awaitable[httpx.Response]],
    monotonic_ms: Optional[Callable[[], float]] = None,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    epoch_ms: Optional[Callable[[], float]] = None,
) -> DocumentStatus:
    pinned_attempt_id = attempt_id
    last_status: Optional[DocumentStatus] = None

    if _is_cancelled(cancel_event):
        raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)

    now_mono = monotonic_ms or (lambda: time.monotonic() * 1000.0)
    now_epoch = epoch_ms or (lambda: time.time() * 1000.0)
    deadline = now_mono() + float(timeout_ms)

    async def _sleep(delay_ms: float) -> None:
        if sleep_fn is not None:
            await sleep_fn(delay_ms)
            return
        delay_s = delay_ms / 1000.0
        if isinstance(cancel_event, asyncio.Event):
            try:
                await asyncio.wait_for(cancel_event.wait(), timeout=delay_s)
            except asyncio.TimeoutError:
                pass
        elif isinstance(cancel_event, threading.Event):
            end = time.monotonic() + delay_s
            while not cancel_event.is_set():
                rem = end - time.monotonic()
                if rem <= 0:
                    break
                await asyncio.sleep(min(0.02, rem))
        else:
            await asyncio.sleep(delay_s)

    while True:
        if _is_cancelled(cancel_event):
            raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)
        remaining_ms = deadline - now_mono()
        if remaining_ms <= 0:
            raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)

        try:
            resp, cancelled = await _fetch_cancellable_async(
                fetch_once, remaining_ms / 1000.0, cancel_event
            )
        except httpx.TimeoutException as exc:
            if _is_cancelled(cancel_event):
                raise DocumentWaitCancelledError(
                    document_uid, pinned_attempt_id, last_status
                ) from exc
            raise DocumentWaitTimeoutError(
                document_uid, pinned_attempt_id, last_status
            ) from exc

        if cancelled or resp is None or _is_cancelled(cancel_event):
            raise DocumentWaitCancelledError(document_uid, pinned_attempt_id, last_status)

        body = _parse_response_body(resp)
        if resp.status_code == 200:
            status = validate_document_status_payload(body, 200)
            last_status = status
            ready, pinned_attempt_id = _evaluate_200_status(
                document_uid, until, pinned_attempt_id, status
            )
            if ready:
                return status
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            delay_ms = _compute_backoff_ms(
                resp.headers.get("retry-after"),
                interval_ms,
                remaining_after,
                now_epoch(),
            )
            if delay_ms is None:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            await _sleep(delay_ms)
            continue

        code = body.get("code") if isinstance(body, dict) else None
        if resp.status_code == 409 and code == "status_changed":
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            await _sleep(min(float(interval_ms), remaining_after))
            continue

        if resp.status_code == 429 or (
            resp.status_code == 503 and _permits_503_retry(body)
        ):
            remaining_after = deadline - now_mono()
            if remaining_after <= 0:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            delay_ms = _compute_backoff_ms(
                resp.headers.get("retry-after"),
                interval_ms,
                remaining_after,
                now_epoch(),
            )
            if delay_ms is None:
                raise DocumentWaitTimeoutError(document_uid, pinned_attempt_id, last_status)
            await _sleep(delay_ms)
            continue

        raise MindGraphError(
            f"GET {path} failed: {resp.status_code}",
            resp.status_code,
            body,
        )

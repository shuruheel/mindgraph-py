"""T-RL15: Offline unit + mock-HTTP conformance tests for Document Readiness
Lifecycle (`document-status.v1`) in the Python SDK (sync + async).
"""

from __future__ import annotations

import asyncio
import datetime
import email.utils
import threading
from typing import Any

import httpx
import pytest

from mindgraph import (
    DOCUMENT_STATUS_CONTRACT,
    AsyncMindGraph,
    DocumentIncompleteError,
    DocumentStatus,
    DocumentSupersededError,
    DocumentWaitCancelledError,
    DocumentWaitTimeoutError,
    MindGraph,
    MindGraphError,
    ReadinessNotRequestedError,
    ReadinessUnknownError,
    ValidationError,
)
from mindgraph.document_lifecycle import (
    parse_retry_after_ms,
    run_wait_for_document_async,
    run_wait_for_document_sync,
)

BASE_URL = "https://api.mindgraph.test"


def make_status(**overrides: Any) -> DocumentStatus:
    base: dict[str, Any] = {
        "contract": DOCUMENT_STATUS_CONTRACT,
        "document_uid": "doc-1",
        "document_version": 2,
        "generation_id": "gen_01",
        "attempt_id": "att_01",
        "job_id": "job_01",
        "job_available": True,
        "processing_status": "processing",
        "attempt_state": "running",
        "content_revision": "sha256:abc",
        "pipeline_digest": "sha256:def",
        "readiness": {
            "lexical": "ready",
            "vector": "not_ready",
            "extraction": "not_ready",
        },
        "observed_at": "2026-11-22T04:00:00Z",
        "error": None,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def make_sync_client(
    responses: list[httpx.Response],
    calls: list[httpx.Request],
) -> MindGraph:
    idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        pos = min(idx["i"], len(responses) - 1)
        idx["i"] += 1
        return responses[pos]

    client = MindGraph(BASE_URL, api_key="mg_test")
    client._client = httpx.Client(
        base_url=client.base_url,
        headers={"Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def make_async_client(
    responses: list[httpx.Response],
    calls: list[httpx.Request],
) -> AsyncMindGraph:
    idx = {"i": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        pos = min(idx["i"], len(responses) - 1)
        idx["i"] += 1
        return responses[pos]

    client = AsyncMindGraph(BASE_URL, api_key="mg_test")
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        headers={"Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def assert_strictly_read_only(
    calls: list[httpx.Request], expected_path: str = "/ingest/document/doc-1/status"
) -> None:
    for req in calls:
        assert req.method == "GET"
        assert req.url.path == expected_path


# ── Validation, Receipts, and get_document_status ─────────────────────


def test_sync_and_async_timeout_bounds_reject_immediately_with_zero_http_calls():
    calls: list[httpx.Request] = []
    client = make_sync_client([httpx.Response(200, json=make_status())], calls)
    for bad in [0, -1, 300_001, True, False, 100.5]:
        with pytest.raises(ValidationError) as exc_info:
            client.wait_for_document("doc-1", timeout_ms=bad)  # type: ignore[arg-type]
        assert exc_info.value.code == "validation_error"
        assert isinstance(exc_info.value, ValueError)
        assert isinstance(exc_info.value, MindGraphError)

    with pytest.raises(ValidationError):
        client.wait_for_document("doc-1", until="bad")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        client.wait_for_document("doc-1", attempt_id="")
    assert len(calls) == 0
    client.close()


def test_sync_resume_document_forwards_reprocess_and_receipt_fields():
    calls: list[httpx.Request] = []
    receipt = {
        "job_id": "job-2",
        "document_uid": "doc-1",
        "chunks_to_resume": 2,
        "total_chunks": 5,
        "generation_id": "gen_02",
        "attempt_id": "att_02",
    }
    client = make_sync_client([httpx.Response(202, json=receipt)], calls)
    res = client.resume_document("doc/1", layers=["reality"], reprocess=True)
    assert res == receipt
    assert calls[0].url.raw_path == b"/ingest/resume/doc%2F1"
    assert calls[0].content == b'{"layers":["reality"],"reprocess":true}' or (
        b'"reprocess": true' in calls[0].content or b'"reprocess":true' in calls[0].content
    )
    client.close()


def test_sync_get_document_status_url_encodes_and_validates_contract():
    calls: list[httpx.Request] = []
    status = make_status(document_uid="doc/a?b#c")
    client = make_sync_client(
        [
            httpx.Response(200, json=status),
            httpx.Response(200, json={"contract": "wrong", "document_uid": "doc-1"}),
        ],
        calls,
    )
    assert client.get_document_status("doc/a?b#c") == status
    assert calls[0].url.raw_path == b"/ingest/document/doc%2Fa%3Fb%23c/status"

    with pytest.raises(MindGraphError) as exc_info:
        client.get_document_status("doc-1")
    assert exc_info.value.code == "incompatible_response"
    client.close()


# ── Sync T-RL15 scenarios ─────────────────────────────────────────────


def test_sync_wait_for_document_explicit_pin_and_auto_pin_superseded():
    # Explicit pin reaches ready
    calls: list[httpx.Request] = []
    client = make_sync_client(
        [
            httpx.Response(200, json=make_status(attempt_id="att_01", attempt_state="running")),
            httpx.Response(
                200,
                json=make_status(
                    attempt_id="att_01",
                    attempt_state="completed",
                    processing_status="completed",
                    readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
                ),
            ),
        ],
        calls,
    )
    done = client.wait_for_document(
        "doc-1", attempt_id="att_01", until="extraction", interval_ms=100, timeout_ms=5_000
    )
    assert done["readiness"]["extraction"] == "ready"
    assert len(calls) == 2
    assert_strictly_read_only(calls)
    client.close()

    # Auto-pin first non-null attempt_id, then superseded on second poll
    calls2: list[httpx.Request] = []
    superseded_status = make_status(
        attempt_id="att_02",
        attempt_state="completed",
        readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
    )
    client2 = make_sync_client(
        [
            httpx.Response(200, json=make_status(attempt_id="att_01", attempt_state="running")),
            httpx.Response(200, json=superseded_status),
        ],
        calls2,
    )
    with pytest.raises(DocumentSupersededError) as exc_info:
        client2.wait_for_document("doc-1", interval_ms=100, timeout_ms=5_000)
    err = exc_info.value
    assert err.code == "document_superseded"
    assert err.document_uid == "doc-1"
    assert err.expected_attempt_id == "att_01"
    assert err.observed_attempt_id == "att_02"
    assert err.last_status == superseded_status
    assert_strictly_read_only(calls2)
    client2.close()


def test_sync_legacy_not_requested_and_attempt_state_classification():
    # Legacy (attempt_id: null) -> ReadinessUnknownError
    legacy = make_status(
        generation_id=None,
        attempt_id=None,
        job_id=None,
        job_available=False,
        attempt_state=None,
        processing_status="completed",
        readiness={"lexical": "unknown", "vector": "unknown", "extraction": "unknown"},
    )
    calls: list[httpx.Request] = []
    client = make_sync_client([httpx.Response(200, json=legacy)], calls)
    with pytest.raises(ReadinessUnknownError) as exc_info:
        client.wait_for_document("doc-1", timeout_ms=5_000)
    assert exc_info.value.code == "readiness_unknown"
    assert exc_info.value.document_uid == "doc-1"
    assert exc_info.value.last_status == legacy
    client.close()

    # not_requested -> ReadinessNotRequestedError
    no_vec = make_status(
        readiness={"lexical": "ready", "vector": "not_requested", "extraction": "not_ready"}
    )
    client2 = make_sync_client([httpx.Response(200, json=no_vec)], [])
    with pytest.raises(ReadinessNotRequestedError) as exc_info2:
        client2.wait_for_document("doc-1", until="vector", timeout_ms=5_000)
    assert exc_info2.value.code == "readiness_not_requested"
    assert exc_info2.value.dimension == "vector"
    assert exc_info2.value.last_status == no_vec
    client2.close()

    # Active attempt_state='running' continues even when processing_status is stale ('failed')
    calls3: list[httpx.Request] = []
    client3 = make_sync_client(
        [
            httpx.Response(
                200,
                json=make_status(
                    processing_status="failed",
                    attempt_state="running",
                    readiness={"lexical": "ready", "vector": "ready", "extraction": "not_ready"},
                ),
            ),
            httpx.Response(
                200,
                json=make_status(
                    processing_status="completed",
                    attempt_state="completed",
                    readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
                ),
            ),
        ],
        calls3,
    )
    res = client3.wait_for_document("doc-1", interval_ms=100, timeout_ms=5_000)
    assert res["readiness"]["extraction"] == "ready"
    assert len(calls3) == 2
    client3.close()

    # Terminal not_ready -> DocumentIncompleteError (even if processing_status says 'processing')
    interrupted = make_status(
        processing_status="processing",
        attempt_state="interrupted",
        readiness={"lexical": "ready", "vector": "not_ready", "extraction": "not_ready"},
    )
    client4 = make_sync_client([httpx.Response(200, json=interrupted)], [])
    with pytest.raises(DocumentIncompleteError) as exc_info4:
        client4.wait_for_document("doc-1", until="vector", timeout_ms=5_000)
    assert exc_info4.value.code == "document_incomplete"
    assert exc_info4.value.dimension == "vector"
    assert exc_info4.value.last_status == interrupted
    client4.close()

    # Terminal unknown -> ReadinessUnknownError
    unknown = make_status(
        attempt_state="completed",
        readiness={"lexical": "unknown", "vector": "unknown", "extraction": "unknown"},
    )
    client5 = make_sync_client([httpx.Response(200, json=unknown)], [])
    with pytest.raises(ReadinessUnknownError):
        client5.wait_for_document("doc-1", until="extraction", timeout_ms=5_000)
    client5.close()


def test_sync_409_status_changed_and_retry_after_clamping():
    # 409 status_changed retries transparently
    calls: list[httpx.Request] = []
    client = make_sync_client(
        [
            httpx.Response(
                409,
                json={"error": "changed", "code": "status_changed", "retriable": True},
            ),
            httpx.Response(
                200,
                json=make_status(
                    attempt_state="completed",
                    readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
                ),
            ),
        ],
        calls,
    )
    done = client.wait_for_document("doc-1", attempt_id="att_01", interval_ms=100, timeout_ms=5_000)
    assert done["readiness"]["extraction"] == "ready"
    assert len(calls) == 2
    assert_strictly_read_only(calls)
    client.close()

    # Retry-After parsing (seconds + HTTP-date)
    base_dt = datetime.datetime(2026, 11, 22, 4, 0, 0, tzinfo=datetime.timezone.utc)
    base_ms = base_dt.timestamp() * 1000.0
    assert parse_retry_after_ms("4", base_ms) == 4_000
    assert parse_retry_after_ms("0", base_ms) == 0
    future_http = email.utils.format_datetime(
        base_dt + datetime.timedelta(seconds=5), usegmt=True
    )
    assert parse_retry_after_ms(future_http, base_ms) == 5_000
    assert parse_retry_after_ms("invalid-header", base_ms) is None

    # Fake-clock clamping: 429 Retry-After=2s sleeps 2000ms, 200 Retry-After=+1s sleeps 1000ms, then ready
    now = {"ms": base_ms}
    sleeps: list[float] = []
    seq = [
        httpx.Response(429, json={"code": "rate_limited"}, headers={"Retry-After": "2"}),
        httpx.Response(
            200,
            json=make_status(attempt_state="running"),
            headers={
                "Retry-After": email.utils.format_datetime(
                    base_dt + datetime.timedelta(seconds=3), usegmt=True
                )
            },
        ),
        httpx.Response(
            200,
            json=make_status(
                attempt_state="completed",
                readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
            ),
        ),
    ]
    idx = {"i": 0}

    def fake_fetch(_rem: float) -> httpx.Response:
        r = seq[idx["i"]]
        idx["i"] += 1
        return r

    def fake_sleep(ms: float) -> None:
        sleeps.append(ms)
        now["ms"] += ms

    res = run_wait_for_document_sync(
        document_uid="doc-1",
        path="/ingest/document/doc-1/status",
        attempt_id=None,
        until="extraction",
        timeout_ms=10_000,
        interval_ms=100,
        cancel_event=None,
        fetch_once=fake_fetch,
        monotonic_ms=lambda: now["ms"],
        sleep_fn=fake_sleep,
        epoch_ms=lambda: now["ms"],
    )
    assert res["readiness"]["extraction"] == "ready"
    assert sleeps == [2_000.0, 1_000.0]

    # Retry-After >= remaining_ms raises DocumentWaitTimeoutError immediately without exceeding deadline
    now2 = {"ms": base_ms}
    sleeps2: list[float] = []
    running = make_status(attempt_state="running")
    seq2 = [
        httpx.Response(200, json=running),
        httpx.Response(503, json={"code": "overloaded"}, headers={"Retry-After": "60"}),
    ]
    idx2 = {"i": 0}

    def fake_fetch2(_rem: float) -> httpx.Response:
        r = seq2[idx2["i"]]
        idx2["i"] += 1
        return r

    def fake_sleep2(ms: float) -> None:
        sleeps2.append(ms)
        now2["ms"] += ms

    with pytest.raises(DocumentWaitTimeoutError) as exc_timeout:
        run_wait_for_document_sync(
            document_uid="doc-1",
            path="/ingest/document/doc-1/status",
            attempt_id=None,
            until="extraction",
            timeout_ms=500,
            interval_ms=100,
            cancel_event=None,
            fetch_once=fake_fetch2,
            monotonic_ms=lambda: now2["ms"],
            sleep_fn=fake_sleep2,
            epoch_ms=lambda: now2["ms"],
        )
    assert exc_timeout.value.code == "document_wait_timeout"
    assert exc_timeout.value.document_uid == "doc-1"
    assert exc_timeout.value.attempt_id == "att_01"
    assert exc_timeout.value.last_status == running
    assert sleeps2 == [100.0]
    assert now2["ms"] - base_ms <= 500.0


def test_sync_timeout_and_cancel_event_send_zero_write_or_cancel_requests():
    running = make_status(attempt_state="running")
    calls: list[httpx.Request] = []
    client = make_sync_client([httpx.Response(200, json=running)], calls)

    # Timeout
    with pytest.raises(DocumentWaitTimeoutError) as exc_t:
        client.wait_for_document("doc-1", interval_ms=100, timeout_ms=150)
    assert exc_t.value.document_uid == "doc-1"
    assert exc_t.value.attempt_id == "att_01"
    assert exc_t.value.last_status == running
    assert len(calls) >= 1
    assert_strictly_read_only(calls)

    # Pre-set cancel_event -> 0 requests
    calls_pre: list[httpx.Request] = []
    client_pre = make_sync_client([httpx.Response(200, json=running)], calls_pre)
    ev = threading.Event()
    ev.set()
    with pytest.raises(DocumentWaitCancelledError) as exc_c:
        client_pre.wait_for_document("doc-1", attempt_id="att_01", cancel_event=ev, timeout_ms=5_000)
    assert exc_c.value.code == "document_wait_cancelled"
    assert exc_c.value.document_uid == "doc-1"
    assert exc_c.value.attempt_id == "att_01"
    assert exc_c.value.last_status is None
    assert len(calls_pre) == 0

    # Cancel during sleep after first poll -> preserves last_status, 0 writes
    calls_mid: list[httpx.Request] = []
    ev_mid = threading.Event()

    def handler_mid(request: httpx.Request) -> httpx.Response:
        calls_mid.append(request)
        threading.Timer(0.02, ev_mid.set).start()
        return httpx.Response(200, json=running)

    client_mid = MindGraph(BASE_URL, api_key="mg_test")
    client_mid._client = httpx.Client(
        base_url=client_mid.base_url,
        transport=httpx.MockTransport(handler_mid),
    )
    with pytest.raises(DocumentWaitCancelledError) as exc_mid:
        client_mid.wait_for_document("doc-1", interval_ms=1_000, timeout_ms=10_000, cancel_event=ev_mid)
    assert exc_mid.value.document_uid == "doc-1"
    assert exc_mid.value.attempt_id == "att_01"
    assert exc_mid.value.last_status == running
    assert len(calls_mid) == 1
    assert_strictly_read_only(calls_mid)

    client.close()
    client_pre.close()
    client_mid.close()


# ── Async T-RL15 parity scenarios ─────────────────────────────────────


@pytest.mark.asyncio
async def test_async_wait_for_document_full_parity():
    # 1. Validation rejects before any HTTP call
    calls: list[httpx.Request] = []
    async with make_async_client([httpx.Response(200, json=make_status())], calls) as client:
        for bad in [0, 300_001]:
            with pytest.raises(ValidationError):
                await client.wait_for_document("doc-1", timeout_ms=bad)
        assert len(calls) == 0

    # 2. 409 status_changed + running -> ready with explicit attempt_id
    calls2: list[httpx.Request] = []
    async with make_async_client(
        [
            httpx.Response(409, json={"code": "status_changed", "retriable": True}),
            httpx.Response(200, json=make_status(attempt_id="att_01", attempt_state="running")),
            httpx.Response(
                200,
                json=make_status(
                    attempt_id="att_01",
                    attempt_state="completed",
                    readiness={"lexical": "ready", "vector": "ready", "extraction": "ready"},
                ),
            ),
        ],
        calls2,
    ) as client2:
        status = await client2.wait_for_document(
            "doc-1", attempt_id="att_01", interval_ms=100, timeout_ms=5_000
        )
        assert status["readiness"]["extraction"] == "ready"
        assert len(calls2) == 3
        assert_strictly_read_only(calls2)

    # 3. Superseded attempt detection
    calls3: list[httpx.Request] = []
    async with make_async_client(
        [httpx.Response(200, json=make_status(attempt_id="att_99"))], calls3
    ) as client3:
        with pytest.raises(DocumentSupersededError) as exc_sup:
            await client3.wait_for_document("doc-1", attempt_id="att_01", timeout_ms=5_000)
        assert exc_sup.value.expected_attempt_id == "att_01"
        assert exc_sup.value.observed_attempt_id == "att_99"

    # 4. asyncio.Event cancellation during sleep preserves last_status and sends 0 writes
    cancel = asyncio.Event()
    running = make_status(attempt_state="running")
    calls4: list[httpx.Request] = []

    async def cancel_handler(request: httpx.Request) -> httpx.Response:
        calls4.append(request)
        asyncio.get_running_loop().call_later(0.02, cancel.set)
        return httpx.Response(200, json=running)

    async with AsyncMindGraph(BASE_URL, api_key="mg_test") as client4:
        client4._client = httpx.AsyncClient(
            base_url=client4.base_url,
            transport=httpx.MockTransport(cancel_handler),
        )
        with pytest.raises(DocumentWaitCancelledError) as exc_can:
            await client4.wait_for_document(
                "doc-1", interval_ms=1_000, timeout_ms=10_000, cancel_event=cancel
            )
        assert exc_can.value.document_uid == "doc-1"
        assert exc_can.value.attempt_id == "att_01"
        assert exc_can.value.last_status == running
        assert len(calls4) == 1
        assert_strictly_read_only(calls4)

    # 5. Async fake-clock Retry-After clamping to deadline
    base_ms = 1_763_784_000_000.0
    now = {"ms": base_ms}
    sleeps: list[float] = []

    async def fake_async_fetch(_rem: float) -> httpx.Response:
        return httpx.Response(429, json={"code": "rate_limited"}, headers={"Retry-After": "120"})

    async def fake_async_sleep(ms: float) -> None:
        sleeps.append(ms)
        now["ms"] += ms

    with pytest.raises(DocumentWaitTimeoutError) as exc_ra:
        await run_wait_for_document_async(
            document_uid="doc-1",
            path="/ingest/document/doc-1/status",
            attempt_id="att_01",
            until="extraction",
            timeout_ms=500,
            interval_ms=100,
            cancel_event=None,
            fetch_once=fake_async_fetch,
            monotonic_ms=lambda: now["ms"],
            sleep_fn=fake_async_sleep,
            epoch_ms=lambda: now["ms"],
        )
    assert exc_ra.value.document_uid == "doc-1"
    assert exc_ra.value.attempt_id == "att_01"
    assert sleeps == []


def test_python39_type_hints_and_edge_cases():
    import typing
    from mindgraph import (
        DocumentStatusError,
        DocumentStatusReadiness,
    )
    from mindgraph.document_lifecycle import validate_wait_params

    # Python 3.9 compatibility: get_type_hints must succeed AND raw annotations must not use PEP 604 '|'
    for target in (
        DocumentStatus,
        DocumentStatusReadiness,
        DocumentStatusError,
        MindGraph.get_document_status,
        MindGraph.wait_for_document,
        AsyncMindGraph.get_document_status,
        AsyncMindGraph.wait_for_document,
    ):
        hints = typing.get_type_hints(target)
        assert hints
        for ann in getattr(target, "__annotations__", {}).values():
            if isinstance(ann, str):
                assert "|" not in ann, f"PEP 604 union found in {target}: {ann}"

    # Non-ASCII digit in Retry-After returns None instead of raising ValueError
    assert parse_retry_after_ms("²") is None
    assert parse_retry_after_ms("٣") is None

    # interval_ms clamping (< 100 -> 100) and invalid interval_ms rejection
    assert validate_wait_params(
        attempt_id=None, until="extraction", timeout_ms=1_000, interval_ms=10
    )[3] == 100
    for bad_iv in (True, False, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            validate_wait_params(
                attempt_id=None,
                until="extraction",
                timeout_ms=1_000,
                interval_ms=bad_iv,  # type: ignore[arg-type]
            )

    # Missing/non-string attempt_id fails closed with incompatible_response
    bad_payload = {
        "contract": DOCUMENT_STATUS_CONTRACT,
        "document_uid": "doc-1",
        "attempt_state": "completed",
        "readiness": {"lexical": "ready", "vector": "ready", "extraction": "ready"},
    }
    client = make_sync_client([httpx.Response(200, json=bad_payload)], [])
    with pytest.raises(MindGraphError) as exc_inc:
        client.wait_for_document("doc-1", timeout_ms=5_000)
    assert exc_inc.value.code == "incompatible_response"

    # Non-status_changed 409, 404, and non-retriable 503 propagate immediately
    for status_code, body in [
        (409, {"code": "other_conflict", "retriable": False}),
        (404, {"code": "not_found"}),
        (503, {"code": "overloaded", "retriable": False}),
        (503, {"code": "vector_index_rebuilding"}),
    ]:
        calls: list[httpx.Request] = []
        c = make_sync_client([httpx.Response(status_code, json=body)], calls)
        with pytest.raises(MindGraphError) as exc_err:
            c.wait_for_document("doc-1", timeout_ms=5_000)
        assert exc_err.value.status == status_code
        assert len(calls) == 1
        c.close()

    # httpx.TimeoutException on per-request timeout maps to DocumentWaitTimeoutError
    seen_timeouts: list[float] = []

    def timeout_fetch(rem_s: float) -> httpx.Response:
        seen_timeouts.append(rem_s)
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(DocumentWaitTimeoutError) as exc_to:
        run_wait_for_document_sync(
            document_uid="doc-1",
            path="/ingest/document/doc-1/status",
            attempt_id="att_01",
            until="extraction",
            timeout_ms=250,
            interval_ms=100,
            cancel_event=None,
            fetch_once=timeout_fetch,
        )
    assert exc_to.value.attempt_id == "att_01"
    assert len(seen_timeouts) == 1 and 0 < seen_timeouts[0] <= 0.25
    client.close()


@pytest.mark.asyncio
async def test_async_in_flight_cancellation_and_threading_event():
    # 1. asyncio.Event cancels an in-flight slow HTTP request immediately
    cancel = asyncio.Event()
    started = asyncio.Event()

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(10.0)
        return httpx.Response(200, json=make_status())

    async with AsyncMindGraph(BASE_URL, api_key="mg_test") as client:
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(slow_handler),
        )

        async def trigger_cancel() -> None:
            await started.wait()
            cancel.set()

        trigger = asyncio.create_task(trigger_cancel())
        t0 = asyncio.get_running_loop().time()
        with pytest.raises(DocumentWaitCancelledError) as exc_can:
            await client.wait_for_document(
                "doc-1", attempt_id="att_01", timeout_ms=30_000, cancel_event=cancel
            )
        elapsed = asyncio.get_running_loop().time() - t0
        await trigger
        assert exc_can.value.document_uid == "doc-1"
        assert exc_can.value.attempt_id == "att_01"
        assert exc_can.value.last_status is None
        assert elapsed < 1.0

    # 2. threading.Event also cancels an in-flight AsyncMindGraph request
    th_cancel = threading.Event()
    started2 = asyncio.Event()

    async def slow_handler2(request: httpx.Request) -> httpx.Response:
        started2.set()
        await asyncio.sleep(10.0)
        return httpx.Response(200, json=make_status())

    async with AsyncMindGraph(BASE_URL, api_key="mg_test") as client2:
        client2._client = httpx.AsyncClient(
            base_url=client2.base_url,
            transport=httpx.MockTransport(slow_handler2),
        )

        async def trigger_th_cancel() -> None:
            await started2.wait()
            th_cancel.set()

        trigger2 = asyncio.create_task(trigger_th_cancel())
        t0 = asyncio.get_running_loop().time()
        with pytest.raises(DocumentWaitCancelledError):
            await client2.wait_for_document(
                "doc-1", attempt_id="att_01", timeout_ms=30_000, cancel_event=th_cancel
            )
        elapsed2 = asyncio.get_running_loop().time() - t0
        await trigger2
        assert elapsed2 < 1.0

import json

import httpx
import pytest

from mindgraph import MindGraph, MindGraphError


@pytest.fixture
def transport(monkeypatch):
    clients = []

    def make(body, status=503, hint="86400", **kwargs):
        calls, sleeps = [], []
        monkeypatch.setattr("mindgraph.client.time.sleep", sleeps.append)

        def handle(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(status, json=body, headers={"Retry-After": hint})
            return httpx.Response(200, json={})

        client = MindGraph("https://offline.invalid", **kwargs)
        client._client.close()
        client._client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handle))
        clients.append(client)
        return client, calls, sleeps

    yield make
    for client in clients:
        client.close()


@pytest.mark.parametrize("status,code", [
    (503, "vector_index_rebuilding"), (503, "query_admission_busy"),
    (422, "query_memory_budget_exceeded"), (504, "query_timeout"), (409, "query_cancelled"),
])
def test_explicit_false_preserves_fields_and_stops_retry(transport, status, code):
    body = {"error": "Operation failed", "code": code, "retriable": False}
    client, calls, sleeps = transport(body, status)
    with pytest.raises(MindGraphError) as caught:
        client.hybrid_search("test")
    assert (caught.value.status, caught.value.code, caught.value.retriable) == (status, code, False)
    assert caught.value.body == body
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("body", ["busy", {}, {"retriable": True}, [], None])
def test_legacy_and_allowed_reads_retry(transport, body):
    client, calls, sleeps = transport(body)
    client.hybrid_search("test")
    assert len(calls) == 2
    assert sleeps == [10.0]


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/reality/capture", {"action": "source", "label": "source"}),
    ("POST", "/agent/plan", {"action": "create_task", "idempotency_key": "ignored"}),
    ("POST", "/agent/plan", {"action": "heartbeat", "idempotency_key": " "}),
    ("POST", "/reality/series", {"action": "append"}),
    ("POST", "/retrieve", {"action": "future_action"}),
    ("PATCH", "/node/n", {"label": "updated"}), ("DELETE", "/node/n", None),
])
def test_unprotected_writes_do_not_retry_even_with_server_hint(transport, method, path, body):
    client, calls, sleeps = transport({"retriable": True})
    with pytest.raises(MindGraphError):
        client._request(method, path, json=body)
    assert len(calls) == 1
    assert sleeps == []


def test_keyed_work_retries_with_same_payload(transport, monkeypatch):
    client, calls, _ = transport({"code": "query_admission_busy", "retriable": True})
    body = {"action": "heartbeat", "idempotency_key": "key-1", "task_uid": "t"}
    monkeypatch.setattr("mindgraph.client.time.sleep", lambda _: body.update(idempotency_key="changed"))
    client._request("POST", "/agent/plan", json=body)
    assert len(calls) == 2
    assert calls[0].content == calls[1].content
    assert json.loads(calls[1].content)["idempotency_key"] == "key-1"


def test_false_also_stops_keyed_work(transport):
    client, calls, sleeps = transport({"retriable": False})
    with pytest.raises(MindGraphError):
        client._request("POST", "/agent/plan", json={"action": "heartbeat", "idempotency_key": "k"})
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("hint", ["NaN", "Infinity", "-1", "invalid", ""])
def test_fallback_delay_is_bounded(transport, hint):
    client, calls, sleeps = transport("busy", hint=hint, retry_backoff=60.0)
    client.health()
    assert len(calls) == 2
    assert sleeps == [10.0]


def test_terminal_maintenance_code_without_flag(transport):
    client, calls, sleeps = transport({"code": "vector_index_rebuilding"})
    with pytest.raises(MindGraphError):
        client.health()
    assert len(calls) == 1
    assert sleeps == []


def test_malformed_guidance_stays_untyped():
    error = MindGraphError("failed", 503, {"code": 3, "retriable": "false"})
    assert error.code is None and error.retriable is None

import json
from dataclasses import FrozenInstanceError

import httpx
import pytest

from mindgraph import MindGraph, MindGraphError

SCOPE = {"space_uid": "space:project:alpha"}

def make_client(handler):
    client = MindGraph(base_url="http://memory.test", max_retries=0)
    client._client = httpx.Client(base_url="http://memory.test", transport=httpx.MockTransport(handler))
    return client

def reply(body, status=200, contract="memory.v1"):
    return httpx.Response(status, json=body, headers={"x-mindgraph-contract": contract})

def test_binding_and_key_preservation():
    calls = []
    def handler(request):
        calls.append(request)
        return reply({"contract": "memory.v1", "scope": SCOPE, "uid": "m1"}, 201)
    memory = make_client(handler).memory(space_uid=SCOPE["space_uid"])
    assert not calls
    with pytest.raises(FrozenInstanceError):
        memory.space_uid = "other"
    memory.remember("deploy to staging", custom_id="deploy-target")
    assert json.loads(calls[0].content) == {"scope": SCOPE, "text": "deploy to staging", "custom_id": "deploy-target"}
    assert calls[0].url.path == "/memory/v1/remember"

def test_domain_404_preserved_without_discovery():
    calls = []
    def handler(request):
        calls.append(request)
        return reply({"error": "missing", "code": "scope_not_found"}, 404)
    with pytest.raises(MindGraphError) as error:
        make_client(handler).memory(space_uid=SCOPE["space_uid"]).list()
    assert error.value.code == "scope_not_found"
    assert len(calls) == 1

@pytest.mark.parametrize("discovery,expected", [
    (reply({"contracts": []}), "unsupported_capability"),
    (reply({"error": "missing"}, 404, ""), "endpoint_unavailable"),
    (reply({"contracts": []}, 302), "endpoint_unavailable"),
])
def test_discovery_never_replays_mutation(discovery, expected):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(404, text="missing") if len(calls) == 1 else discovery
    with pytest.raises(MindGraphError) as error:
        make_client(handler).memory(space_uid=SCOPE["space_uid"]).remember("text")
    assert error.value.code == expected
    assert [r.url.path for r in calls] == ["/memory/v1/remember", "/memory/v1"]

@pytest.mark.parametrize("body", [
    {"contract": "memory.v0", "scope": SCOPE},
    {"contract": "memory.v1", "scope": {"space_uid": "other"}},
    {"contract": "memory.v1", "scope": SCOPE, "project_uid": "unexpected"},
])
def test_incompatible_success_refused(body):
    with pytest.raises(MindGraphError) as error:
        make_client(lambda request: reply(body)).memory(space_uid=SCOPE["space_uid"]).list()
    assert error.value.code == "incompatible_response"

def test_facade_retry_freezes_nested_filter(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    predicate = {"field": "salience", "op": "gt", "value": 0.5}
    calls = []
    def handler(request):
        calls.append(request.content)
        if len(calls) == 1:
            predicate["value"] = 0.9
            return reply({"code": "query_admission_busy", "retriable": True}, 503)
        return reply({"contract": "memory.v1", "scope": SCOPE, "items": [], "next_cursor": None})
    client = make_client(handler)
    client._max_retries = 1
    client.memory(space_uid=SCOPE["space_uid"]).list(node_filter=predicate)
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert json.loads(calls[1])["node_filter"]["value"] == 0.5

def test_facade_mutations_do_not_retry_server_hints():
    calls = []
    def handler(request):
        calls.append(request)
        return reply({"code": "query_admission_busy", "retriable": True}, 503)
    client = make_client(handler)
    client._max_retries = 3
    memory = client.memory(space_uid=SCOPE["space_uid"])
    for operation in [lambda: memory.remember("safe", custom_id="key"), lambda: memory.forget(custom_id="key")]:
        with pytest.raises(MindGraphError):
            operation()
    assert len(calls) == 2

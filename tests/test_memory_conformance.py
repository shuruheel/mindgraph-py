"""Identical captured server requests/responses also exercised by the TS SDK."""
import json
from pathlib import Path

import httpx
import pytest

from mindgraph import MindGraph, MindGraphError

FIXTURES = json.loads((Path(__file__).parents[1] / "fixtures/memory-v1.json").read_text())

@pytest.mark.parametrize("fixture", FIXTURES["cases"], ids=lambda f: f["name"])
def test_shared_server_wire_fixture(fixture):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/memory/v1/" + fixture["operation"]
        assert json.loads(request.content) == fixture["request"]
        return httpx.Response(fixture["status"], json=fixture["response"], headers={"x-mindgraph-contract": "memory.v1"})
    with MindGraph(base_url="http://memory.test", max_retries=0) as client:
        client._client.close()
        client._client = httpx.Client(base_url="http://memory.test", transport=httpx.MockTransport(handler))
        options = dict(fixture["request"])
        memory = client.memory(space_uid=options.pop("scope")["space_uid"])
        operation = getattr(memory, fixture["operation"])
        if fixture["status"] < 300:
            assert operation(**options) == fixture["response"]
        else:
            with pytest.raises(MindGraphError) as error:
                operation(**options)
            assert error.value.status == fixture["status"]
            assert error.value.code == fixture["response"]["code"]
        assert len(calls) == 1

def test_write_response_models_cover_the_captured_contract():
    from typing import get_type_hints

    from mindgraph.memory import ForgetResponse, RememberResponse

    models = {"remember": RememberResponse, "forget": ForgetResponse}
    for fixture in FIXTURES["cases"]:
        model = models.get(fixture["operation"])
        if model and fixture["status"] < 300:
            assert set(fixture["response"]) <= set(get_type_hints(model))
    undo = get_type_hints(ForgetResponse)["undo"]
    assert get_type_hints(undo) == {"node": str}

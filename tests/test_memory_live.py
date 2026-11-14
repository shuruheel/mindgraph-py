"""Opt-in offline server fixture, not a production integration test."""
import os

import pytest

from mindgraph import MindGraph

BASE_URL = os.environ.get("MEMORY_CONFORMANCE_URL")

@pytest.mark.skipif(not BASE_URL, reason="local memory_conformance example is not running")
def test_public_sdk_workflow():
    with MindGraph(base_url=BASE_URL, max_retries=0) as client:
        assert "memory.v1" in client.contracts()["contracts"]
        memory = client.memory(space_uid="space:python-conformance")
        saved = memory.remember("Use the staging cluster", custom_id="deploy-target")
        context = memory.context(query="staging", article_limit=0, chunk_limit=0, ontology={"mode": "off"}, format="text", max_tokens=1000)
        assert context["budget"]["used"] <= 1000
        assert saved["uid"] in [item["uid"] for item in memory.list()["items"]]
        assert saved["uid"] in [item["uid"] for item in memory.profile()["profile"]["memories"]]
        memory.forget(custom_id="deploy-target")
        assert memory.profile()["profile"]["memories"] == []

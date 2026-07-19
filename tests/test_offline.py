"""Offline wire-contract parity tests for the MindGraph Python SDK.

These tests hit NO network. They install an ``httpx.MockTransport`` into the
client's underlying ``httpx.Client`` to capture the outgoing request, then
assert the request path / HTTP method / JSON body ``action`` + required fields
match the canonical contract in ``tests/contract_fixture.py`` (derived from
CLAUDE.md, verified against the server by R6).

Run: ``pytest tests/test_offline.py`` — no API key, no secrets, no network.

KNOWN R4 DIVERGENCES (a pending owner/product decision, NOT bugs to fix here)
are pinned in ``test_known_r4_divergences`` so they are documented and do not
fail CI; any NEW/undocumented drift from the contract DOES fail.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from mindgraph import MindGraph

from .contract_fixture import (
    CONTRACT,
    FIELD_CONVENTIONS,
    MONOLITHIC_ENDPOINTS,
    PASSTHROUGH,
    VALID_ACTIONS,
)

BASE_URL = "https://api.mindgraph.test"


class Capture:
    """Records the single request a method makes through MockTransport."""

    def __init__(self) -> None:
        self.request: httpx.Request | None = None

    @property
    def path(self) -> str:
        assert self.request is not None, "no request was captured"
        return self.request.url.path

    @property
    def full_path(self) -> str:
        assert self.request is not None, "no request was captured"
        url = self.request.url
        return url.path + (("?" + url.query.decode()) if url.query else "")

    @property
    def method(self) -> str:
        assert self.request is not None
        return self.request.method

    @property
    def body(self) -> dict[str, Any]:
        assert self.request is not None
        content = self.request.content
        if not content:
            return {}
        return json.loads(content)


def make_client(capture: Capture, response_json: Any = None) -> MindGraph:
    """Build a MindGraph client whose transport records and replies offline."""

    def handler(request: httpx.Request) -> httpx.Response:
        capture.request = request
        payload = {"uid": "n_test"} if response_json is None else response_json
        return httpx.Response(200, json=payload)

    client = MindGraph(BASE_URL, api_key="mg_test_key")
    # Swap the real transport for an offline mock; never touches the network.
    client._client = httpx.Client(
        base_url=client.base_url,
        headers={"Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_ontology_review_filters_and_schema_actions_are_exposed():
    cap = Capture()
    client = make_client(cap, response_json={"items": [], "limit": 50, "offset": 0})
    client.list_ontology_proposals(
        schema_id="schema-1",
        proposal_type="semantic_match_candidate",
        extract_job_id="job-1",
    )
    assert cap.method == "GET"
    assert "schema_id=schema-1" in cap.full_path
    assert "proposal_type=semantic_match_candidate" in cap.full_path
    assert "extract_job_id=job-1" in cap.full_path

    client.analyze_ontology_semantic_guidance("schema-1")
    assert cap.method == "POST"
    assert cap.path == "/v1/ontology/schemas/schema-1/semantic-guidance/analyze"

    client.audit_ontology_duplicates("schema-1")
    assert cap.method == "POST"
    assert cap.path == "/v1/ontology/schemas/schema-1/duplicates/audit"
    client.close()


# ---------------------------------------------------------------------------
# Sanity: the fixture itself is internally consistent.
# ---------------------------------------------------------------------------


def test_retrieve_action_set_is_exact():
    """The /retrieve action enum is the most drift-prone invariant."""
    assert VALID_ACTIONS["/retrieve"] == {
        "text",
        "semantic",
        "hybrid",
        "active_goals",
        "open_questions",
        "weak_claims",
        "pending_approvals",
        "unresolved_contradictions",
        "merge_candidates",
        "curation_counts",
        "stale_derivations",
        "preferences",
        "layer",
        "recent",
    }


def test_fixture_actions_are_valid_for_their_endpoint():
    """Every contract entry's declared action belongs to its endpoint's set."""
    for entry in CONTRACT:
        action = entry["action"]
        path = entry["path"]
        if action is None:
            assert path in MONOLITHIC_ENDPOINTS
            continue
        if path in VALID_ACTIONS:
            assert action in VALID_ACTIONS[path], (
                f"{entry['method']} declares action={action!r} "
                f"not in valid set for {path}"
            )


# ---------------------------------------------------------------------------
# Per-method wire parity: every CONTRACT entry.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", CONTRACT, ids=[e["method"] for e in CONTRACT])
def test_contract_method_wire_shape(entry: dict):
    cap = Capture()
    client = make_client(cap)
    method = getattr(client, entry["method"])

    positional = entry.get("positional", [])
    kwargs = entry.get("args", {})
    method(*positional, **kwargs)

    # HTTP method.
    assert cap.method == entry["http_method"], (
        f"{entry['method']}: expected {entry['http_method']}, got {cap.method}"
    )

    # Path (exact or substring).
    if "path" in entry:
        assert cap.path == entry["path"], (
            f"{entry['method']}: expected path {entry['path']}, got {cap.path}"
        )
    elif "path_contains" in entry:
        assert entry["path_contains"] in cap.full_path

    body = cap.body

    # Action: present, correct, and a valid member of the endpoint set.
    if entry["action"] is not None:
        assert body.get("action") == entry["action"], (
            f"{entry['method']}: expected action {entry['action']}, "
            f"got {body.get('action')}"
        )
        path = entry.get("path")
        if path in VALID_ACTIONS:
            assert body["action"] in VALID_ACTIONS[path]
    else:
        # Monolithic endpoints must not carry an action field.
        assert "action" not in body, (
            f"{entry['method']}: monolithic endpoint must not send action"
        )

    # Required fields present.
    for field in entry["required_fields"]:
        assert field in body, (
            f"{entry['method']}: missing required field {field!r} in body {body}"
        )

    # Forbidden (anti-convention) fields absent.
    for field in entry.get("forbidden_fields", []):
        assert field not in body, (
            f"{entry['method']}: forbidden field {field!r} present in body {body}"
        )

    client.close()


# ---------------------------------------------------------------------------
# Passthrough (**kwargs) methods: action is supplied by the caller and must
# land in the body unchanged, on the right path, within the valid set.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", PASSTHROUGH, ids=[e["method"] for e in PASSTHROUGH])
def test_passthrough_method_forwards_action(entry: dict):
    cap = Capture()
    client = make_client(cap)
    method = getattr(client, entry["method"])

    method(action=entry["action"], label="x", summary="y")

    assert cap.method == "POST"
    assert cap.path == entry["path"]
    body = cap.body
    assert body.get("action") == entry["action"]
    assert body["action"] in VALID_ACTIONS[entry["path"]]
    client.close()


# ---------------------------------------------------------------------------
# Field-name conventions (SDK-Server Field Name Conventions in CLAUDE.md).
# ---------------------------------------------------------------------------


def test_traverse_uses_start_uid_not_uid_or_from_uid():
    cap = Capture()
    client = make_client(cap)
    client.traverse(action="chain", start_uid="n_1", max_depth=2)
    body = cap.body
    assert body.get(FIELD_CONVENTIONS["traverse_start_uid"]) == "n_1"
    assert "uid" not in body
    assert "from_uid" not in body
    client.close()


def test_traverse_path_uses_end_uid_not_to_uid():
    cap = Capture()
    client = make_client(cap)
    client.traverse(action="path", start_uid="n_1", end_uid="n_2")
    body = cap.body
    assert body.get("action") == "path"
    assert body.get(FIELD_CONVENTIONS["traverse_start_uid"]) == "n_1"
    assert body.get(FIELD_CONVENTIONS["traverse_path_end_uid"]) == "n_2"
    assert "to_uid" not in body
    client.close()


def test_reasoning_chain_shortcut_uses_start_uid():
    cap = Capture()
    client = make_client(cap, response_json={"steps": []})
    client.reasoning_chain("n_1", max_depth=3)
    body = cap.body
    assert cap.path == "/traverse"
    assert body == {"action": "chain", "start_uid": "n_1", "max_depth": 3}
    client.close()


def test_retrieve_context_forwards_budgeted_expansion_options():
    cap = Capture()
    client = make_client(cap, response_json={"graph": {"nodes": [], "edges": []}})
    client.retrieve_context(
        "graph retrieval",
        node_limit=18,
        graph_expansion_limit=6,
        graph_max_depth=3,
        valid_at="2026-07-17",
    )
    assert cap.path == "/retrieve/context"
    assert cap.body == {
        "query": "graph retrieval",
        "node_limit": 18,
        "graph_expansion_limit": 6,
        "graph_max_depth": 3,
        "valid_at": "2026-07-17",
    }
    client.close()


@pytest.mark.parametrize(
    ("method", "expected_path"),
    [
        (lambda client: client.search("scope", project_uid="project-1"), "/search"),
        (
            lambda client: client.hybrid_search("scope", project_uid="project-1"),
            "/retrieve",
        ),
        (
            lambda client: client.ingest_document("scope", project_uid="project-1"),
            "/ingest/document",
        ),
        (
            lambda client: client.retrieve_context("scope", project_uid="project-1"),
            "/retrieve/context",
        ),
    ],
)
def test_project_uid_wire_contract(method, expected_path):
    cap = Capture()
    client = make_client(cap, response_json=[])
    method(client)
    assert cap.path == expected_path
    assert cap.body["project_uid"] == "project-1"
    client.close()


# ---------------------------------------------------------------------------
# /epistemic/argument is MONOLITHIC: no action; structured claim + evidence
# (evidence is an ARRAY per the server's ArgumentRequest contract).
# ---------------------------------------------------------------------------


def test_argue_is_monolithic_no_action_evidence_array():
    cap = Capture()
    client = make_client(cap, response_json={"claim_uid": "c_1"})
    client.argue(
        claim={"label": "C", "statement": "s"},
        evidence=[{"label": "E", "statement": "e"}],
    )
    body = cap.body
    assert cap.path == "/epistemic/argument"
    assert "action" not in body  # monolithic
    assert "claim" in body
    assert isinstance(body["evidence"], list)  # server contract: evidence is array
    client.close()


# ---------------------------------------------------------------------------
# The full /retrieve action set is reachable through the raw retrieve() method
# (the Python RetrieveRequest is untyped **kwargs, so all 14 are accepted).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", sorted(VALID_ACTIONS["/retrieve"]))
def test_retrieve_accepts_every_valid_action(action: str):
    cap = Capture()
    client = make_client(cap, response_json=[])
    client.retrieve(action=action)
    body = cap.body
    assert cap.path == "/retrieve"
    assert body.get("action") == action
    client.close()


def test_retrieve_includes_merge_candidates_and_curation_counts():
    """These two are valid server-side but omitted from the TS enum (R4 #3).
    Python's untyped kwargs accept both — assert they reach the wire."""
    for action in ("merge_candidates", "curation_counts"):
        cap = Capture()
        client = make_client(cap, response_json=[])
        client.retrieve(action=action)
        assert cap.body.get("action") == action
        client.close()


# ---------------------------------------------------------------------------
# Auth header wiring (verifies the client still sets Bearer auth offline).
# ---------------------------------------------------------------------------


def test_api_key_sets_bearer_auth_header():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": "ok"})

    client = MindGraph(BASE_URL, api_key="mg_secret")
    client._client = httpx.Client(
        base_url=client.base_url,
        headers={"Authorization": "Bearer mg_secret"},
        transport=httpx.MockTransport(handler),
    )
    client.health()
    assert captured["auth"] == "Bearer mg_secret"
    client.close()


# ===========================================================================
# KNOWN R4 DIVERGENCES — pinned, documented, NON-failing.
#
# These restate the *current* Python behavior that diverges from the TS SDK
# and/or the canonical reconciliation R4 will eventually land. R4 is a pending
# owner/product decision (a confirmed breaking change), so these tests assert
# present behavior so the divergence is visible and intentional in CI, while
# any UNDOCUMENTED drift still fails the contract tests above.
# ===========================================================================

# Allowlist: human-readable record of each pinned divergence.
KNOWN_DIVERGENCES = [
    "R4#1 add_claim -> POST /epistemic/inquiry action=hypothesis -> Hypothesis "
    "(TS addClaim -> POST /epistemic/argument -> Claim). Different endpoint AND node type.",
    "R4#2 add_evidence sends a single OBJECT under 'evidence' with 'summary' "
    "(TS addEvidence sends an ARRAY + props).",
    "R4#3 Python retrieve() accepts merge_candidates and curation_counts "
    "(TS RetrieveRequest.action omits both, though both are valid server-side).",
    "R4#4 get_article_by_subject maps ONLY 404 -> None and re-raises other errors "
    "(TS getArticleBySubject swallows ALL errors as not-found).",
    "R4#5 Python client has a 30s default timeout (TS request() has no timeout).",
]


def test_known_divergence_1_add_claim_routes_to_inquiry_hypothesis():
    cap = Capture()
    client = make_client(cap)
    client.add_claim("Label", "content", confidence=0.8)
    body = cap.body
    # Diverges from TS: Py uses /epistemic/inquiry + hypothesis, NOT /epistemic/argument.
    assert cap.path == "/epistemic/inquiry"
    assert body.get("action") == "hypothesis"
    assert body.get("label") == "Label"
    assert body.get("summary") == "content"
    client.close()


def test_known_divergence_2_add_evidence_sends_single_object():
    cap = Capture()
    client = make_client(cap, response_json={"uid": "e_1"})
    client.add_evidence("Evidence label", "the description")
    body = cap.body
    assert cap.path == "/epistemic/argument"
    # Diverges from TS array form: Py sends a single dict object + summary.
    assert isinstance(body.get("evidence"), dict)
    assert body["evidence"]["label"] == "Evidence label"
    assert body["evidence"]["summary"] == "the description"
    client.close()


def test_known_divergence_3_retrieve_accepts_ts_omitted_actions():
    for action in ("merge_candidates", "curation_counts"):
        cap = Capture()
        client = make_client(cap, response_json=[])
        client.retrieve(action=action)
        assert cap.body.get("action") == action
        client.close()


def test_known_divergence_4_get_article_by_subject_404_only():
    # 404 -> None
    def handler_404(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = MindGraph(BASE_URL, api_key="mg_test")
    client._client = httpx.Client(
        base_url=client.base_url, transport=httpx.MockTransport(handler_404)
    )
    assert client.get_article_by_subject("subj_1") is None
    client.close()

    # 500 -> re-raised (NOT swallowed, unlike TS).
    def handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    from mindgraph import MindGraphError

    client2 = MindGraph(BASE_URL, api_key="mg_test")
    client2._client = httpx.Client(
        base_url=client2.base_url, transport=httpx.MockTransport(handler_500)
    )
    with pytest.raises(MindGraphError):
        client2.get_article_by_subject("subj_1")
    client2.close()


def test_known_divergence_5_default_timeout_is_30s():
    # Build a normal client (real transport, but we never send a request) and
    # inspect its configured timeout — Python default is 30s; TS has none.
    client = MindGraph(BASE_URL, api_key="mg_test")
    assert client._client.timeout.read == 30.0
    client.close()


def test_known_divergences_documented():
    """Guard: the allowlist stays populated so divergences remain visible."""
    assert len(KNOWN_DIVERGENCES) == 5
    assert all(d.startswith("R4#") for d in KNOWN_DIVERGENCES)

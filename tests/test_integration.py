"""
Comprehensive integration tests for the MindGraph Python SDK.
Tests every public method against the live Cloud API.

Run: API_KEY=mg_live_... pytest tests/test_integration.py -v
"""
import os
import pytest

from mindgraph import MindGraph

API_KEY = os.environ.get("API_KEY") or os.environ.get("MINDGRAPH_API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "https://api.mindgraph.cloud")

pytestmark = pytest.mark.skipif(not API_KEY, reason="API_KEY not set")


@pytest.fixture(scope="module")
def mg():
    client = MindGraph(BASE_URL, api_key=API_KEY)
    yield client
    client.close()


@pytest.fixture(scope="module")
def uids():
    """Shared UIDs across tests in this module."""
    return {}


# ============================================================
# 1. Health & Stats
# ============================================================
class TestHealthStats:
    def test_health(self, mg):
        r = mg.health()
        assert r["status"] == "ok"

    def test_stats(self, mg):
        r = mg.stats()
        assert "live_nodes" in r


# ============================================================
# 2. Management
# ============================================================
class TestManagement:
    def test_list_api_keys(self, mg):
        r = mg.list_api_keys()
        assert "api_keys" in r

    def test_get_usage(self, mg):
        r = mg.get_usage()
        assert "org_id" in r


# ============================================================
# 3. Reality: Capture
# ============================================================
class TestRealityCapture:
    def test_source(self, mg, uids):
        r = mg.capture(
            action="source",
            label="PY SDK Test Source",
            summary="Integration test source",
            props={"uri": "https://example.com", "title": "Example"},
        )
        assert "uid" in r
        uids["source"] = r["uid"]

    def test_snippet(self, mg, uids):
        r = mg.capture(
            action="snippet",
            label="PY SDK Test Snippet",
            summary="A snippet from the source",
            source_uid=uids["source"],
        )
        assert "uid" in r

    def test_observation(self, mg, uids):
        r = mg.capture(
            action="observation",
            label="PY SDK Test Observation",
            summary="Something observed during testing",
            props={"content": "The SDK is working well"},
        )
        assert "uid" in r
        uids["observation"] = r["uid"]


# ============================================================
# 4. Reality: Entity
# ============================================================
class TestRealityEntity:
    def test_create(self, mg, uids):
        r = mg.entity(
            action="create",
            label="PY SDK Test Entity",
            summary="A test entity",
            props={"canonical_name": "py-test-entity", "entity_type": "concept"},
        )
        assert "uid" in r
        uids["entity"] = r["uid"]

    def test_alias(self, mg, uids):
        r = mg.entity(
            action="alias",
            text="py-sdk-entity-alias",
            canonical_uid=uids["entity"],
        )
        assert r is not None

    def test_resolve(self, mg, uids):
        r = mg.entity(action="resolve", text="py-sdk-entity-alias")
        assert r is not None

    def test_relate(self, mg, uids):
        r = mg.entity(
            action="relate",
            source_uid=uids["entity"],
            target_uid=uids["observation"],
            edge_type="Related",
        )
        assert r is not None

    def test_find_or_create_entity(self, mg, uids):
        r = mg.find_or_create_entity("PY SDK Find-or-Create", {"canonical_name": "py-foc"})
        assert "uid" in r
        uids["foc_entity"] = r["uid"]

    def test_merge(self, mg, uids):
        # Create two fresh entities for merge (don't touch the shared entity)
        e1 = mg.entity(
            action="create",
            label="PY Merge Winner",
            summary="Will survive",
            props={"canonical_name": "py-merge-winner"},
        )
        e2 = mg.entity(
            action="create",
            label="PY Merge Loser",
            summary="Will be merged",
            props={"canonical_name": "py-merge-loser"},
        )
        r = mg.entity(
            action="merge",
            keep_uid=e1["uid"],
            merge_uid=e2["uid"],
        )
        assert r is not None


# ============================================================
# 5. Epistemic: Inquiry
# ============================================================
class TestEpistemicInquiry:
    def test_hypothesis(self, mg):
        r = mg.inquire(
            action="hypothesis",
            label="PY Hypothesis",
            summary="If we test, quality improves",
            props={"statement": "Testing leads to quality"},
        )
        assert "uid" in r

    def test_theory(self, mg):
        r = mg.inquire(action="theory", label="PY Theory", summary="Theory of reliability")
        assert "uid" in r

    def test_question(self, mg):
        r = mg.inquire(
            action="question",
            label="PY Question",
            summary="How to improve?",
            props={"question": "How to improve coverage?"},
        )
        assert "uid" in r

    def test_open_question(self, mg):
        r = mg.inquire(
            action="open_question",
            label="PY Open Question",
            summary="What is quality?",
            props={"question": "What is quality?"},
        )
        assert "uid" in r

    def test_assumption(self, mg):
        r = mg.inquire(action="assumption", label="PY Assumption", summary="Tests are pure")
        assert "uid" in r

    def test_anomaly(self, mg):
        r = mg.inquire(action="anomaly", label="PY Anomaly", summary="Unexpected pass")
        assert "uid" in r

    def test_paradigm(self, mg):
        r = mg.inquire(action="paradigm", label="PY Paradigm", summary="TDD paradigm")
        assert "uid" in r


# ============================================================
# 6. Epistemic: Argument
# ============================================================
class TestEpistemicArgument:
    def test_argue(self, mg, uids):
        r = mg.argue(
            claim={"label": "PY Claim", "statement": "SDKs need tests"},
            evidence=[{"label": "PY Evidence", "statement": "Data shows bugs in untested SDKs"}],
        )
        assert "claim_uid" in r
        uids["claim"] = r["claim_uid"]


# ============================================================
# 7. Epistemic: Structure
# ============================================================
class TestEpistemicStructure:
    @pytest.mark.parametrize(
        "action",
        [
            "concept",
            "pattern",
            "mechanism",
            "model",
            "model_evaluation",
            "analogy",
            "inference_chain",
            "reasoning_strategy",
            "sensitivity_analysis",
            "theorem",
            "equation",
            "method",
            "experiment",
        ],
    )
    def test_structure_actions(self, mg, action):
        r = mg.structure(action=action, label=f"PY {action}", summary=f"Test {action}")
        assert "uid" in r


# ============================================================
# 8. Intent: Commitment
# ============================================================
class TestIntentCommitment:
    def test_goal(self, mg, uids):
        r = mg.commit(action="goal", label="PY Goal", summary="Complete tests")
        assert "uid" in r
        uids["goal"] = r["uid"]

    def test_project(self, mg, uids):
        r = mg.commit(
            action="project",
            label="PY Project",
            summary="SDK test project",
            parent_uid=uids["goal"],
        )
        assert "uid" in r
        uids["project"] = r["uid"]

    def test_milestone(self, mg, uids):
        r = mg.commit(
            action="milestone",
            label="PY Milestone",
            summary="All green",
            parent_uid=uids["project"],
        )
        assert "uid" in r


# ============================================================
# 9. Intent: Deliberation
# ============================================================
class TestIntentDeliberation:
    def test_open_decision(self, mg, uids):
        r = mg.deliberate(
            action="open_decision",
            label="PY Decision",
            summary="Which framework?",
        )
        assert "uid" in r
        uids["decision"] = r["uid"]

    def test_add_option(self, mg, uids):
        r = mg.deliberate(
            action="add_option",
            label="Option: pytest",
            summary="Use pytest",
            decision_uid=uids["decision"],
        )
        assert "uid" in r

    def test_add_constraint(self, mg, uids):
        r = mg.deliberate(
            action="add_constraint",
            label="Must be fast",
            summary="Under 60s",
            decision_uid=uids["decision"],
        )
        assert "uid" in r

    def test_resolve(self, mg, uids):
        # Create an option to choose
        opt = mg.deliberate(
            action="add_option",
            label="Option: unittest",
            summary="Use unittest",
            decision_uid=uids["decision"],
        )
        r = mg.deliberate(
            action="resolve",
            label="Chose pytest",
            summary="pytest selected",
            decision_uid=uids["decision"],
            chosen_option_uid=opt["uid"],
            props={"decision_rationale": "pytest is standard"},
        )
        assert r is not None

    def test_get_open(self, mg):
        r = mg.deliberate(action="get_open")
        assert r is not None


# ============================================================
# 10. Action: Procedure
# ============================================================
class TestActionProcedure:
    def test_create_flow(self, mg, uids):
        r = mg.procedure(action="create_flow", label="PY Flow", summary="Test workflow")
        assert "uid" in r
        uids["flow"] = r["uid"]

    def test_add_step(self, mg, uids):
        r = mg.procedure(
            action="add_step",
            label="Step 1",
            summary="Setup",
            flow_uid=uids["flow"],
        )
        assert "uid" in r

    def test_add_affordance(self, mg):
        r = mg.procedure(
            action="add_affordance",
            label="PY Affordance",
            summary="Can test",
            props={"action_name": "run_tests"},
        )
        assert "uid" in r

    def test_add_control(self, mg):
        r = mg.procedure(
            action="add_control",
            label="PY Control",
            summary="Lint first",
            props={"condition": "lint passes", "action": "allow"},
        )
        assert "uid" in r


# ============================================================
# 11. Action: Risk
# ============================================================
class TestActionRisk:
    def test_assess(self, mg):
        r = mg.risk(
            action="assess",
            label="PY Risk",
            summary="Untested code paths",
            props={"vulnerability": "gaps", "mitigation": "more tests"},
        )
        assert "uid" in r

    def test_get_assessments(self, mg):
        r = mg.risk(action="get_assessments")
        assert r is not None


# ============================================================
# 12. Memory: Session
# ============================================================
class TestMemorySession:
    def test_open(self, mg, uids):
        r = mg.session(action="open", label="PY Session", summary="Test session")
        assert "uid" in r
        uids["session"] = r["uid"]

    def test_journal(self, mg, uids):
        r = mg.journal(
            "PY Journal Entry",
            {"content": "Testing journal"},
            session_uid=uids["session"],
        )
        assert "uid" in r

    def test_trace(self, mg, uids):
        r = mg.session(
            action="trace",
            label="PY Trace",
            summary="Debug",
            session_uid=uids["session"],
        )
        assert "uid" in r

    def test_close(self, mg, uids):
        r = mg.session(action="close", session_uid=uids["session"])
        assert r is not None


# ============================================================
# 13. Memory: Distill & Config
# ============================================================
class TestMemoryDistillConfig:
    def test_distill(self, mg, uids):
        r = mg.distill(
            label="PY Lesson",
            summary="Tests catch bugs",
            source_uids=[uids["observation"]],
        )
        assert "uid" in r

    def test_set_preference(self, mg):
        r = mg.memory_config(
            action="set_preference",
            label="PY Pref",
            summary="Verbose output",
            props={"key": "verbosity", "value": "high"},
        )
        assert "uid" in r

    def test_set_policy(self, mg):
        r = mg.memory_config(
            action="set_policy",
            label="PY Policy",
            summary="Test first",
            props={"principle": "test before commit"},
        )
        assert "uid" in r

    def test_get_preferences(self, mg):
        r = mg.memory_config(action="get_preferences")
        assert r is not None

    def test_get_policies(self, mg):
        r = mg.memory_config(action="get_policies")
        assert r is not None


# ============================================================
# 14. Agent: Plan
# ============================================================
class TestAgentPlan:
    def test_create_task(self, mg):
        r = mg.plan(action="create_task", label="PY Task", summary="Do something")
        assert "uid" in r

    def test_create_plan(self, mg, uids):
        r = mg.plan(action="create_plan", label="PY Plan", summary="Master plan")
        assert "uid" in r
        uids["plan"] = r["uid"]

    def test_add_step(self, mg, uids):
        r = mg.plan(
            action="add_step",
            label="Plan Step",
            summary="Setup",
            plan_uid=uids["plan"],
        )
        assert "uid" in r

    def test_get_plan(self, mg, uids):
        r = mg.plan(action="get_plan", plan_uid=uids["plan"])
        assert r is not None


# ============================================================
# 15. Agent: Governance
# ============================================================
class TestAgentGovernance:
    def test_set_budget(self, mg):
        r = mg.governance(
            action="set_budget",
            label="PY Budget",
            summary="Resource limits",
            props={"description": "Budget"},
        )
        assert "uid" in r

    def test_create_policy(self, mg):
        r = mg.governance(
            action="create_policy", label="PY Gov Policy", summary="Safety first"
        )
        assert "uid" in r

    def test_request_approval(self, mg, uids):
        r = mg.governance(
            action="request_approval",
            label="PY Approval",
            summary="Need approval",
        )
        assert "uid" in r
        uids["approval"] = r["uid"]

    def test_resolve_approval(self, mg, uids):
        r = mg.governance(
            action="resolve_approval",
            approval_uid=uids["approval"],
            approved=True,
        )
        assert r is not None

    def test_get_pending(self, mg):
        r = mg.governance(action="get_pending")
        assert r is not None


# ============================================================
# 16. Agent: Execution
# ============================================================
class TestAgentExecution:
    def test_start(self, mg, uids):
        r = mg.execution(action="start", label="PY Execution", summary="Running")
        assert "uid" in r
        uids["execution"] = r["uid"]

    def test_complete(self, mg, uids):
        r = mg.execution(
            action="complete",
            label="Done",
            summary="Passed",
            execution_uid=uids["execution"],
        )
        assert r is not None

    def test_fail(self, mg):
        start = mg.execution(action="start", label="PY Fail Exec", summary="Will fail")
        r = mg.execution(
            action="fail",
            label="Failed",
            summary="Error",
            execution_uid=start["uid"],
        )
        assert r is not None

    def test_register_agent(self, mg):
        r = mg.execution(
            action="register_agent",
            label="PY Test Agent",
            summary="Integration test agent",
        )
        assert "uid" in r

    def test_get_executions(self, mg):
        r = mg.execution(action="get_executions")
        assert r is not None


# ============================================================
# 17. Retrieve
# ============================================================
class TestRetrieve:
    def test_text(self, mg):
        r = mg.retrieve(action="text", query="test", limit=3)
        assert r is not None

    def test_active_goals(self, mg):
        r = mg.retrieve(action="active_goals")
        assert r is not None

    def test_open_questions(self, mg):
        r = mg.retrieve(action="open_questions")
        assert r is not None

    def test_weak_claims(self, mg):
        r = mg.retrieve(action="weak_claims")
        assert r is not None

    def test_pending_approvals(self, mg):
        r = mg.retrieve(action="pending_approvals")
        assert r is not None

    def test_unresolved_contradictions(self, mg):
        r = mg.retrieve(action="unresolved_contradictions")
        assert r is not None

    def test_layer(self, mg):
        r = mg.retrieve(action="layer", layer="reality", limit=3)
        assert r is not None

    def test_recent(self, mg):
        r = mg.retrieve(action="recent", limit=3)
        assert r is not None


# ============================================================
# 18. Traverse
# ============================================================
class TestTraverse:
    def test_chain(self, mg, uids):
        r = mg.traverse(action="chain", start_uid=uids["entity"], max_depth=2)
        assert r is not None

    def test_neighborhood(self, mg, uids):
        r = mg.traverse(action="neighborhood", start_uid=uids["entity"], max_depth=1)
        assert r is not None

    def test_path(self, mg, uids):
        r = mg.traverse(
            action="path", start_uid=uids["entity"], end_uid=uids["observation"]
        )
        assert r is not None

    def test_subgraph(self, mg, uids):
        r = mg.traverse(action="subgraph", start_uid=uids["entity"], max_depth=1)
        assert r is not None


# ============================================================
# 19. Evolve
# ============================================================
class TestEvolve:
    def test_update(self, mg, uids):
        r = mg.evolve(action="update", uid=uids["entity"], summary="Updated via evolve")
        assert r is not None

    def test_history(self, mg, uids):
        r = mg.evolve(action="history", uid=uids["entity"])
        assert r is not None

    def test_snapshot(self, mg, uids):
        r = mg.evolve(action="snapshot", uid=uids["entity"], version=1)
        assert r is not None

    def test_tombstone_and_restore(self, mg):
        node = mg.capture(action="observation", label="PY Evolve Temp", summary="Temp")
        uid = node["uid"]
        mg.evolve(action="tombstone", uid=uid, reason="test")
        mg.evolve(action="restore", uid=uid)


# ============================================================
# 20. Node CRUD
# ============================================================
class TestNodeCRUD:
    def test_full_lifecycle(self, mg):
        # Create
        node = mg.add_node(
            "PY CRUD Node",
            props={"_type": "Entity", "canonical_name": "py-crud", "description": "test"},
        )
        assert "uid" in node
        uid = node["uid"]

        # Read
        fetched = mg.get_node(uid)
        assert fetched["uid"] == uid

        # Update
        updated = mg.update_node(uid, summary="Updated via CRUD")
        assert updated["summary"] == "Updated via CRUD"

        # Delete
        mg.delete_node(uid)


# ============================================================
# 21. Edge CRUD
# ============================================================
class TestEdgeCRUD:
    def test_add_link_and_get_edges(self, mg, uids):
        link = mg.add_link(uids["entity"], uids["goal"], "Supports")
        assert "uid" in link

        edges = mg.get_edges(from_uid=uids["entity"])
        assert isinstance(edges, list)
        assert len(edges) > 0


# ============================================================
# 22. Search
# ============================================================
class TestSearch:
    def test_full_text_search(self, mg):
        results = mg.search("test")
        assert isinstance(results, list)

    def test_hybrid_search(self, mg):
        results = mg.hybrid_search("SDK integration test")
        assert isinstance(results, list)


# ============================================================
# 23. Traversal Shortcuts
# ============================================================
class TestTraversalShortcuts:
    def test_reasoning_chain(self, mg, uids):
        r = mg.reasoning_chain(uids["entity"])
        assert isinstance(r, list)

    def test_neighborhood(self, mg, uids):
        r = mg.neighborhood(uids["entity"])
        assert isinstance(r, list)


# ============================================================
# 24. Lifecycle Shortcuts
# ============================================================
class TestLifecycleShortcuts:
    def test_tombstone_and_restore(self, mg):
        node = mg.capture(action="observation", label="PY Lifecycle Temp", summary="Temp")
        uid = node["uid"]
        mg.tombstone(uid, "testing shortcuts")
        mg.restore(uid)

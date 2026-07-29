"""Canonical wire-contract fixture for the MindGraph Python SDK.

This is the single source of truth that the offline parity test
(``tests/test_offline.py``) checks the client against. It is derived from the
authoritative contract in ``CLAUDE.md`` ("Cognitive Endpoint Actions" table +
"SDK-Server Field Name Conventions"), which R6 verified matches the server.

Each entry describes the *wire* request a client method must produce:

    {
        "method": "<MindGraph attribute name>",
        "http_method": "GET" | "POST" | "PATCH" | "DELETE" | "PUT",
        "path": "/exact/path",          # leading-slash path the client must hit
        "path_contains": "/fragment",   # OR: a substring the path must contain
                                        #     (for path-templated / query-string URLs)
        "action": "<action>" | None,    # required value of JSON body["action"]
        "required_fields": ["a", "b"],  # keys that must appear in the JSON body
        "args": {...},                  # sample kwargs to call the method with
        "positional": [...],            # sample positional args (optional)
    }

Action-dispatch endpoints must send their ``action`` in the JSON body and that
action must be one of the endpoint's valid values per CLAUDE.md. Field-name
conventions (``start_uid``/``end_uid`` for /traverse; structured monolithic
/epistemic/argument) are asserted here too.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Valid action sets per CLAUDE.md "Cognitive Endpoint Actions (exhaustive)".
# The offline test asserts every contract entry's action is in its endpoint set
# and that the SDK never sends an action outside these sets.
# ---------------------------------------------------------------------------

VALID_ACTIONS: dict[str, set[str]] = {
    "/reality/capture": {"source", "snippet", "observation"},
    "/reality/entity": {
        "create",
        "resolve_identity",
        "alias",
        "resolve",
        "fuzzy_resolve",
        "merge",
        "relate",
    },
    # /epistemic/argument is MONOLITHIC — no action field.
    "/epistemic/inquiry": {
        "hypothesis",
        "theory",
        "paradigm",
        "anomaly",
        "assumption",
        "question",
        "open_question",
    },
    "/epistemic/structure": {
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
    },
    "/intent/commitment": {"goal", "project", "milestone"},
    "/intent/deliberation": {
        "open_decision",
        "add_option",
        "add_constraint",
        "resolve",
        "get_open",
    },
    "/action/procedure": {
        "create_flow",
        "add_step",
        "add_affordance",
        "add_control",
    },
    "/action/risk": {"assess", "get_assessments"},
    "/memory/session": {"open", "trace", "close", "journal"},
    # /memory/distill is MONOLITHIC — no action field.
    "/memory/config": {
        "set_preference",
        "get_preferences",
        "set_policy",
        "get_policies",
    },
    "/memory/sync": {"scan", "begin", "record", "finalize", "status", "abandon"},
    "/agent/plan": {
        "create_task",
        "create_plan",
        "add_step",
        "update_status",
        "get_plan",
        "resume_work",
        "claim_task",
        "heartbeat",
        "start_iteration",
        "checkpoint_iteration",
        "block_task",
        "complete_task",
        "abandon_iteration",
    },
    "/agent/governance": {
        "create_policy",
        "set_budget",
        "request_approval",
        "resolve_approval",
        "get_pending",
        "check",
    },
    "/agent/execution": {
        "start",
        "complete",
        "fail",
        "register_agent",
        "get_executions",
    },
    # The full /retrieve action set — the drift-prone invariant from the task.
    "/retrieve": {
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
    },
    "/traverse": {"chain", "neighborhood", "path", "subgraph"},
    "/evolve": {
        "update",
        "tombstone",
        "restore",
        "decay",
        "history",
        "snapshot",
        "tombstone_edge",
        "restore_edge",
        "tombstone_cascade",
    },
}

# Endpoints that are monolithic (must NOT carry an ``action`` field).
MONOLITHIC_ENDPOINTS: set[str] = {"/epistemic/argument", "/memory/distill"}

# Field-name conventions enforced by the server (SDK-Server Field Name
# Conventions in CLAUDE.md). The offline test asserts these positively.
FIELD_CONVENTIONS = {
    "traverse_start_uid": "start_uid",  # NOT uid / from_uid
    "traverse_path_end_uid": "end_uid",  # NOT to_uid
}


# ---------------------------------------------------------------------------
# Per-method contract entries.
# These cover the action-dispatch convenience/raw methods plus the field-name
# conventions. Pure CRUD / passthrough (**kwargs) methods that don't bake in an
# action are exercised separately or recorded in coverage_gaps.
# ---------------------------------------------------------------------------

CONTRACT: list[dict] = [
    # ---- Reality ----
    {
        "method": "entity",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": [
            "action",
            "label",
            "identity",
            "identity_space_uid",
        ],
        "args": {
            "action": "create",
            "label": "Repository",
            "identity": {
                "namespace": "external.code",
                "key_version": 1,
                "key": {
                    "v": 1,
                    "kind": "repository",
                    "repo_id": "fixture",
                },
            },
            "identity_space_uid": "space:project:fixture",
        },
    },
    {
        "method": "entity",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "resolve_identity",
        "required_fields": ["action", "identity"],
        "args": {
            "action": "resolve_identity",
            "identity": {
                "namespace": "external.code",
                "key_version": 1,
                "key": {
                    "v": 1,
                    "kind": "repository",
                    "repo_id": "fixture",
                },
            },
        },
    },
    {
        "method": "find_or_create_entity",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["Acme Corp"],
        "args": {},
    },
    {
        "method": "find_or_create_person",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["Ada Lovelace"],
        "args": {},
    },
    {
        "method": "find_or_create_organization",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["OpenAI"],
        "args": {},
    },
    {
        "method": "find_or_create_nation",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["France"],
        "args": {},
    },
    {
        "method": "find_or_create_event",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["WWDC 2026"],
        "args": {},
    },
    {
        "method": "find_or_create_place",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["Paris"],
        "args": {},
    },
    {
        "method": "find_or_create_concept",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "create",
        "required_fields": ["action", "label", "props"],
        "positional": ["Entropy"],
        "args": {},
    },
    {
        "method": "add_observation",
        "http_method": "POST",
        "path": "/reality/capture",
        "action": "observation",
        "required_fields": ["action", "label", "summary"],
        "positional": ["Obs", "the sky is blue"],
        "args": {},
    },
    {
        "method": "resolve_entity",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "resolve",
        "required_fields": ["action", "text"],
        "positional": ["Acme"],
        "args": {},
    },
    {
        "method": "fuzzy_resolve_entity",
        "http_method": "POST",
        "path": "/reality/entity",
        "action": "fuzzy_resolve",
        "required_fields": ["action", "text", "limit"],
        "positional": ["Acme"],
        "args": {},
    },
    # ---- Epistemic ----
    {
        "method": "add_claim",
        "http_method": "POST",
        # NOTE: KNOWN R4 DIVERGENCE — Py routes add_claim to /epistemic/inquiry
        # (hypothesis), TS routes addClaim to /epistemic/argument (Claim). The
        # offline test records this via KNOWN_DIVERGENCES, not the action check.
        "path": "/epistemic/inquiry",
        "action": "hypothesis",
        "required_fields": ["action", "label", "summary"],
        "positional": ["Claim label", "claim content"],
        "args": {},
    },
    # ---- Intent ----
    {
        "method": "open_decision",
        "http_method": "POST",
        "path": "/intent/deliberation",
        "action": "open_decision",
        "required_fields": ["action", "label"],
        "positional": ["Pick a DB"],
        "args": {},
    },
    {
        "method": "add_option",
        "http_method": "POST",
        "path": "/intent/deliberation",
        "action": "add_option",
        "required_fields": ["action", "decision_uid", "label"],
        "positional": ["dec_1", "Postgres"],
        "args": {},
    },
    {
        "method": "resolve_decision",
        "http_method": "POST",
        "path": "/intent/deliberation",
        "action": "resolve",
        # The optional resolve fields are asserted as required HERE (this
        # fixture supplies them) so a wire-name typo goes red offline —
        # serde on the server silently drops unknown keys.
        "required_fields": [
            "action",
            "decision_uid",
            "chosen_option_uid",
            "informs_uid",
            "as_of_date",
            "session_id",
            "retrieval_trace_id",
        ],
        "positional": ["dec_1", "opt_1"],
        "args": {
            "informs_uid": ["ctx_1"],
            "as_of_date": "2026-07-17",
            "session_id": "session_7",
            "retrieval_trace_id": "trace_7",
        },
    },
    # ---- Memory ----
    {
        # /memory/distill is MONOLITHIC — no action field. `output_type`
        # ("lesson") and `summarizes_uids` asserted for the same reason as
        # the resolve fields above.
        "method": "distill",
        "http_method": "POST",
        "path": "/memory/distill",
        "action": None,
        "required_fields": ["label", "output_type", "summarizes_uids"],
        "forbidden_fields": ["action"],
        "positional": [],
        "args": {
            "label": "Stage migrations before cutover",
            "summary": "We learned to stage migrations first.",
            "output_type": "lesson",
            "summarizes_uids": ["exec_1"],
        },
    },
    {
        "method": "journal",
        "http_method": "POST",
        "path": "/memory/session",
        "action": "journal",
        "required_fields": ["action", "label"],
        "positional": ["A journal entry"],
        "args": {},
    },
    # ---- Graph-managed work ----
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "create_task",
        "required_fields": ["action", "goal_uid", "related_uids"],
        "positional": [],
        "args": {
            "action": "create_task",
            "goal_uid": "goal_1",
            "related_uids": ["code_1"],
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "create_plan",
        "required_fields": ["action", "goal_uid", "task_uid", "related_uids"],
        "positional": [],
        "args": {
            "action": "create_plan",
            "goal_uid": "goal_1",
            "task_uid": "task_1",
            "related_uids": ["code_1"],
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "add_step",
        "required_fields": ["action", "plan_uid", "depends_on_uids"],
        "positional": [],
        "args": {
            "action": "add_step",
            "plan_uid": "plan_1",
            "depends_on_uids": ["step_0"],
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "update_status",
        "required_fields": ["action", "target_uid", "status"],
        "positional": [],
        "args": {
            "action": "update_status",
            "target_uid": "task_1",
            "status": "in_progress",
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "get_plan",
        "required_fields": ["action", "plan_uid"],
        "positional": [],
        "args": {"action": "get_plan", "plan_uid": "plan_1"},
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "resume_work",
        "required_fields": ["action", "scope_uids", "session_uid"],
        "array_fields": ["scope_uids"],
        "positional": [],
        "args": {
            "action": "resume_work",
            "scope_uids": ["repo_1"],
            "session_uid": "session_1",
            "limit": 1,
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "claim_task",
        "required_fields": [
            "action", "task_uid", "session_uid", "expected_version",
            "idempotency_key",
        ],
        "positional": [],
        "args": {
            "action": "claim_task",
            "task_uid": "task_1",
            "session_uid": "session_1",
            "expected_version": 1,
            "idempotency_key": "claim_1",
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "heartbeat",
        "required_fields": [
            "action", "task_uid", "session_uid", "expected_version",
            "lease_epoch", "idempotency_key",
        ],
        "positional": [],
        "args": {
            "action": "heartbeat",
            "task_uid": "task_1",
            "session_uid": "session_1",
            "expected_version": 2,
            "lease_epoch": 1,
            "idempotency_key": "heartbeat_1",
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "start_iteration",
        "required_fields": [
            "action", "task_uid", "step_uid", "session_uid",
            "expected_version", "lease_epoch", "idempotency_key",
            "input_snapshot",
        ],
        "positional": [],
        "args": {
            "action": "start_iteration",
            "task_uid": "task_1",
            "step_uid": "step_1",
            "session_uid": "session_1",
            "expected_version": 2,
            "lease_epoch": 1,
            "idempotency_key": "start_1",
            "input_snapshot": {"base_commit": "abc"},
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "checkpoint_iteration",
        "required_fields": [
            "action", "task_uid", "execution_uid", "session_uid",
            "expected_version", "lease_epoch", "idempotency_key",
            "output_snapshot", "produces_node_uids",
        ],
        "array_fields": ["produces_node_uids"],
        "positional": [],
        "args": {
            "action": "checkpoint_iteration",
            "task_uid": "task_1",
            "execution_uid": "execution_1",
            "session_uid": "session_1",
            "expected_version": 3,
            "lease_epoch": 1,
            "idempotency_key": "checkpoint_1",
            "output_snapshot": {"head_commit": "def"},
            "produces_node_uids": ["lesson_1"],
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "block_task",
        "required_fields": [
            "action", "task_uid", "session_uid", "expected_version",
            "lease_epoch", "idempotency_key", "release_lease",
        ],
        "positional": [],
        "args": {
            "action": "block_task",
            "task_uid": "task_1",
            "session_uid": "session_1",
            "expected_version": 4,
            "lease_epoch": 1,
            "idempotency_key": "block_1",
            "release_lease": True,
            "summary": "Waiting on dependency",
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "complete_task",
        "required_fields": [
            "action", "task_uid", "execution_uid", "session_uid",
            "expected_version", "lease_epoch", "idempotency_key",
        ],
        "positional": [],
        "args": {
            "action": "complete_task",
            "task_uid": "task_1",
            "execution_uid": "execution_1",
            "session_uid": "session_1",
            "expected_version": 4,
            "lease_epoch": 1,
            "idempotency_key": "complete_1",
        },
    },
    {
        "method": "plan",
        "http_method": "POST",
        "path": "/agent/plan",
        "action": "abandon_iteration",
        "required_fields": [
            "action", "task_uid", "execution_uid", "session_uid",
            "expected_version", "lease_epoch", "idempotency_key",
            "release_lease",
        ],
        "positional": [],
        "args": {
            "action": "abandon_iteration",
            "task_uid": "task_1",
            "execution_uid": "execution_1",
            "session_uid": "session_1",
            "expected_version": 4,
            "lease_epoch": 1,
            "idempotency_key": "abandon_1",
            "release_lease": True,
        },
    },
    {
        "method": "execution",
        "http_method": "POST",
        "path": "/agent/execution",
        "action": "start",
        "required_fields": [
            "action",
            "plan_uid",
            "executor_uid",
            "affordance_uid",
            "related_uids",
            "input_snapshot",
        ],
        "positional": [],
        "args": {
            "action": "start",
            "plan_uid": "plan_1",
            "executor_uid": "agent_1",
            "affordance_uid": "affordance_1",
            "related_uids": ["task_1"],
            "input_snapshot": {"command": "pytest"},
        },
    },
    {
        "method": "execution",
        "http_method": "POST",
        "path": "/agent/execution",
        "action": "complete",
        "required_fields": [
            "action",
            "execution_uid",
            "produces_node_uid",
            "output_snapshot",
            "side_effects",
            "outcome",
        ],
        "positional": [],
        "args": {
            "action": "complete",
            "execution_uid": "execution_1",
            "produces_node_uid": "lesson_1",
            "output_snapshot": {"exit_code": 0},
            "side_effects": ["wrote file"],
            "outcome": "passed",
        },
    },
    {
        "method": "execution",
        "http_method": "POST",
        "path": "/agent/execution",
        "action": "fail",
        "required_fields": [
            "action",
            "execution_uid",
            "output_snapshot",
            "side_effects",
            "outcome",
            "error",
        ],
        "positional": [],
        "args": {
            "action": "fail",
            "execution_uid": "execution_1",
            "output_snapshot": {"exit_code": 1},
            "side_effects": [],
            "outcome": "failed",
            "error": "assertion mismatch",
        },
    },
    {
        "method": "execution",
        "http_method": "POST",
        "path": "/agent/execution",
        "action": "register_agent",
        "required_fields": ["action", "label"],
        "positional": [],
        "args": {"action": "register_agent", "label": "Coding agent"},
    },
    {
        "method": "execution",
        "http_method": "POST",
        "path": "/agent/execution",
        "action": "get_executions",
        "required_fields": ["action", "filter_plan_uid"],
        "positional": [],
        "args": {"action": "get_executions", "filter_plan_uid": "plan_1"},
    },
    {
        "method": "governance",
        "http_method": "POST",
        "path": "/agent/governance",
        "action": "check",
        "required_fields": ["action", "act", "target"],
        "positional": [],
        "args": {
            "action": "check",
            "act": "tool_invoke",
            "target": {
                "tool_name": "mindgraph_plan",
                "action": "complete_execution",
                "mutability": "write",
                "target_uids": ["execution_1"],
            },
        },
    },
    # ---- Cross-cutting / retrieve ----
    {
        "method": "merge_candidates",
        "http_method": "POST",
        "path": "/retrieve",
        "action": "merge_candidates",
        "required_fields": ["action"],
        "positional": [],
        "args": {},
    },
    {
        "method": "stale_derivations",
        "http_method": "POST",
        "path": "/retrieve",
        "action": "stale_derivations",
        "required_fields": ["action"],
        "positional": [],
        "args": {},
    },
    {
        "method": "preferences",
        "http_method": "POST",
        "path": "/retrieve",
        "action": "preferences",
        "required_fields": ["action"],
        "positional": [],
        "args": {},
    },
    {
        "method": "hybrid_search",
        "http_method": "POST",
        "path": "/retrieve",
        "action": "hybrid",
        "required_fields": ["action", "query"],
        "positional": ["graph databases"],
        "args": {},
    },
    # ---- Traverse (field-name conventions) ----
    {
        "method": "reasoning_chain",
        "http_method": "POST",
        "path": "/traverse",
        "action": "chain",
        "required_fields": ["action", "start_uid", "max_depth"],
        "positional": ["n_1"],
        "args": {},
        "forbidden_fields": ["uid", "from_uid"],
    },
    {
        "method": "neighborhood",
        "http_method": "POST",
        "path": "/traverse",
        "action": "neighborhood",
        "required_fields": ["action", "start_uid", "max_depth"],
        "positional": ["n_1"],
        "args": {},
        "forbidden_fields": ["uid", "from_uid"],
    },
    # ---- Evolve shortcuts ----
    {
        "method": "tombstone",
        "http_method": "POST",
        "path": "/evolve",
        "action": "tombstone",
        "required_fields": ["action", "uid"],
        "positional": ["n_1"],
        "args": {},
    },
    {
        "method": "restore",
        "http_method": "POST",
        "path": "/evolve",
        "action": "restore",
        "required_fields": ["action", "uid"],
        "positional": ["n_1"],
        "args": {},
    },
]


# Raw passthrough (**kwargs) methods: the client forwards the body verbatim,
# so the action is supplied by the caller. The offline test drives each with a
# valid action and asserts the path + that the action lands in the body and is a
# member of the endpoint's valid set.
PASSTHROUGH: list[dict] = [
    {"method": "capture", "path": "/reality/capture", "action": "observation"},
    {"method": "entity", "path": "/reality/entity", "action": "create"},
    {"method": "inquire", "path": "/epistemic/inquiry", "action": "hypothesis"},
    {"method": "structure", "path": "/epistemic/structure", "action": "concept"},
    {"method": "commit", "path": "/intent/commitment", "action": "goal"},
    {"method": "deliberate", "path": "/intent/deliberation", "action": "open_decision"},
    {"method": "procedure", "path": "/action/procedure", "action": "create_flow"},
    {"method": "risk", "path": "/action/risk", "action": "assess"},
    {"method": "session", "path": "/memory/session", "action": "open"},
    {"method": "memory_config", "path": "/memory/config", "action": "set_preference"},
    {"method": "memory_sync", "path": "/memory/sync", "action": "scan"},
    {"method": "plan", "path": "/agent/plan", "action": "create_plan"},
    {"method": "governance", "path": "/agent/governance", "action": "create_policy"},
    {"method": "execution", "path": "/agent/execution", "action": "start"},
    {"method": "retrieve", "path": "/retrieve", "action": "text"},
    {"method": "traverse", "path": "/traverse", "action": "chain"},
    {"method": "evolve", "path": "/evolve", "action": "update"},
]

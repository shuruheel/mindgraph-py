"""Reviewed retry semantics; keep the TypeScript SDK's policy in sync."""

from __future__ import annotations

import math
from typing import Any

READ_POSTS = {
    "/search", "/retrieve/context", "/nodes/batch", "/edges/batch", "/subgraph",
    "/embeddings/search", "/embeddings/search-text", "/ontology/query",
    "/ontology/query/structured", "/ontology/objects/search",
}
READ_ACTIONS = {
    "/retrieve": {"text", "semantic", "hybrid", "active_goals", "open_questions",
                  "preferences", "weak_claims", "pending_approvals",
                  "unresolved_contradictions", "merge_candidates", "stale_derivations",
                  "curation_counts", "layer", "recent"},
    "/traverse": {"chain", "top_k_paths", "neighborhood", "path", "subgraph"},
    "/reality/series": {"window", "aggregate", "latest", "list_for_entity",
                        "batch_latest", "batch_aggregate"},
    "/intent/deliberation": {"get_open"},
    "/action/risk": {"get_assessments"},
    "/action/skill": {"get", "list"},
    "/memory/config": {"get_preferences", "get_policies"},
    "/memory/sync": {"status"},
    "/agent/plan": {"get_plan", "resume_work"},
    "/agent/governance": {"get_pending", "check"},
    "/agent/execution": {"get_executions"},
    "/evolve": {"history", "snapshot"},
}
# Receipt and mutation share a transaction. A key on another write does not
# opt it in, and telemetry request IDs never supply an idempotency guarantee.
IDEMPOTENT_WORK = {
    "claim_task", "heartbeat", "start_iteration", "checkpoint_iteration",
    "block_task", "complete_task", "abandon_iteration",
}
TERMINAL_CODES = {
    "query_memory_budget_exceeded", "query_timeout", "query_cancelled",
    "vector_index_rebuilding",
}


def can_retry_request(method: str, path: str, body: Any) -> bool:
    if method in ("GET", "HEAD"):
        return True
    if method != "POST":
        return False
    if path in READ_POSTS:
        return True
    if not isinstance(body, dict) or not isinstance(body.get("action"), str):
        return False
    if body["action"] in READ_ACTIONS.get(path, set()):
        return True
    key = body.get("idempotency_key")
    return (path == "/agent/plan" and body["action"] in IDEMPOTENT_WORK
            and isinstance(key, str) and bool(key.strip()))


def retry_delay(header: str | None, backoff: float, attempt: int) -> float:
    try:
        hint = float(header) if header is not None else 0.0
    except ValueError:
        hint = 0.0
    if math.isfinite(hint) and hint > 0:
        return min(hint, 10.0)
    return min(backoff * (2 ** min(attempt, 32)), 10.0)

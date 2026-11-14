"""Run: mypy --follow-imports=silent --warn-unused-ignores tests/types/memory_contract.py"""
from typing import Literal

from mindgraph.memory import ForgetResponse, RememberResponse


def check_forget(response: ForgetResponse) -> tuple[str, int, int, str]:
    action: Literal["preview", "forgotten"] = response["action"]
    changed: int = response["edges_tombstoned"]
    preview_count: int = response["would_tombstone_edges"]
    restore: str = response["undo"]["node"]
    # The facade guarantees no edge restore receipt; the legacy type differs.
    response["undo"]["edges"]  # type: ignore[typeddict-item]
    return action, changed, preview_count, restore


def check_remember(response: RememberResponse) -> tuple[str, bool, bool]:
    return response["space_uid"], response["embedded"], response["searchable"]["bm25"]

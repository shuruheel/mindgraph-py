"""Explicitly selected, additive memory.v1 API; no I/O during construction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, TypedDict, Union, cast

if TYPE_CHECKING:
    from .client import MindGraph

class TextPredicate(TypedDict):
    field: Literal["node_type", "layer"]
    op: Literal["eq"]
    value: str

class InPredicate(TypedDict):
    field: Literal["node_type", "layer"]
    op: Literal["in"]
    value: list[str]

class NumberPredicate(TypedDict):
    field: Literal["confidence", "salience", "created_at", "updated_at"]
    op: Literal["eq", "gt", "gte", "lt", "lte"]
    value: float

class GroupPredicate(TypedDict):
    op: Literal["and", "or"]
    operands: list[NodeFilter]

NodeFilter = Union[TextPredicate, InPredicate, NumberPredicate, GroupPredicate]
Section = Literal["memories", "preferences", "lessons", "goals", "decisions"]

class Scope(TypedDict):
    space_uid: str

class Budget(TypedDict):
    method: Literal["mindgraph_estimate_v1"]
    limit: int
    used: int
    truncated: bool

class ReadSelection(TypedDict, total=False):
    project_uid: str
    include_org_space: bool

class Envelope(ReadSelection):
    contract: Literal["memory.v1"]
    scope: Scope

class Conflict(TypedDict):
    uid: str
    counterpart_uid: str
    resolution_status: str

class Superseded(TypedDict):
    by: list[str]

class Currency(TypedDict, total=False):
    currently_valid: bool
    valid_from: str
    valid_until: str
    superseded: Superseded
    conflicts: list[Conflict]
    unresolved_evidence: bool
    omitted_reason: Literal["unsafe_summary"]

class MemoryItem(Currency):
    uid: str
    node_type: str
    layer: str
    label: str
    summary: Optional[str]
    text: str
    version: int
    created_at: float
    updated_at: float
    confidence: float
    salience: float
    space_uid: str
    source_uids: list[str]

class ListResponse(Envelope):
    items: list[MemoryItem]
    next_cursor: Optional[str]

class Omissions(TypedDict):
    item_limit: int
    text_budget: int
    unsafe_summary: int

class Unavailable(TypedDict):
    section: Section
    reason: Literal["too_large"]

class ProfileResponse(Envelope):
    profile: dict[Section, list[MemoryItem]]
    computed_at: str
    complete: bool
    omitted: Omissions
    unavailable: list[Unavailable]

class TextProfileResponse(ProfileResponse, total=False):
    context_text: str
    budget: Budget

class Searchable(TypedDict):
    bm25: bool
    vector: bool

class InstructionError(TypedDict):
    code: Optional[str]
    retriable: Optional[bool]

class RememberResponse(Envelope):
    uid: str
    custom_id: Optional[str]
    action: Literal["inserted", "updated", "unchanged", "reused"]
    label: str
    version: int
    space_uid: str
    embedded: bool
    searchable: Searchable
    near_duplicates: list[dict[str, Any]]
    remember_instructions: Optional[str]
    remember_instructions_error: Optional[InstructionError]

class ForgetUndo(TypedDict):
    node: str

class ForgetResponse(Envelope):
    uid: str
    label: str
    dry_run: bool
    cascade: Literal[False]
    edge_uids: list[str]
    action: Literal["preview", "forgotten"]
    edges_tombstoned: int
    would_tombstone_edges: int
    undo: ForgetUndo

class ContextResponse(Envelope, total=False):
    graph: dict[str, list[dict[str, Any]]]
    articles: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
    context_text: str
    budget: Budget
    omitted: dict[str, Any]
    legs_disabled: list[str]
    project_uid: str
    include_org_space: bool

@dataclass(frozen=True)
class MemoryClient:
    _client: MindGraph
    space_uid: str

    def __post_init__(self) -> None:
        if not self.space_uid or self.space_uid != self.space_uid.strip():
            raise ValueError("A nonempty space_uid without surrounding whitespace is required")

    def _call(self, operation: str, options: dict[str, Any]) -> Any:
        from .client import MindGraphError
        body = {key: value for key, value in options.items() if value is not None}
        body["scope"] = {"space_uid": self.space_uid}
        try:
            return self._client._request("POST", f"/memory/v1/{operation}", body)
        except MindGraphError as error:
            if error.code != "endpoint_unavailable":
                raise
            try:
                capabilities = self._client.contracts()
            except MindGraphError as discovery_error:
                if discovery_error.status in (401, 403):
                    raise
                raise error from None
            if "memory.v1" not in capabilities["contracts"]:
                raise MindGraphError("Server does not support memory.v1", error.status,
                                     {"code": "unsupported_capability", "retriable": False}) from error
            raise

    def remember(self, text: str, *, custom_id: Optional[str] = None, label: Optional[str] = None,
                 props: Optional[dict[str, Any]] = None, confidence: Optional[float] = None,
                 salience: Optional[float] = None,
                 on_near_duplicate: Optional[Literal["reuse", "create"]] = None) -> RememberResponse:
        return cast(RememberResponse, self._call("remember", {
            "text": text, "custom_id": custom_id, "label": label, "props": props,
            "confidence": confidence, "salience": salience, "on_near_duplicate": on_near_duplicate}))

    def forget(self, *, uid: Optional[str] = None, custom_id: Optional[str] = None,
               dry_run: bool = False, cascade: Literal[False] = False,
               reason: Optional[str] = None) -> ForgetResponse:
        if bool(uid) == bool(custom_id):
            raise ValueError("Provide exactly one uid or custom_id")
        return cast(ForgetResponse, self._call("forget", {"uid": uid, "custom_id": custom_id,
                    "dry_run": dry_run, "cascade": cascade, "reason": reason}))

    def list(self, *, project_uid: Optional[str] = None, node_filter: Optional[NodeFilter] = None,
             limit: Optional[int] = None, cursor: Optional[str] = None) -> ListResponse:
        return cast(ListResponse, self._call("list", {"project_uid": project_uid,
                    "node_filter": node_filter, "limit": limit, "cursor": cursor}))

    def profile(self, *, project_uid: Optional[str] = None, node_filter: Optional[NodeFilter] = None,
                include_org_space: bool = False, sections: Optional[list[Section]] = None,
                max_items: Optional[int] = None, format: Literal["json", "text"] = "json",
                max_tokens: Optional[int] = None) -> TextProfileResponse:
        return cast(TextProfileResponse, self._call("profile", {"project_uid": project_uid,
                    "node_filter": node_filter, "include_org_space": include_org_space,
                    "sections": sections, "max_items": max_items, "format": format,
                    "max_tokens": max_tokens}))

    def context(self, query: str, *, project_uid: Optional[str] = None,
                include_org_space: bool = False, node_filter: Optional[NodeFilter] = None,
                node_limit: Optional[int] = None, article_limit: Optional[int] = None,
                chunk_limit: Optional[int] = None, node_types: Optional[list[str]] = None,
                layer: Optional[str] = None, graph_expansion_limit: Optional[int] = None,
                graph_max_depth: Optional[int] = None, valid_at: Optional[str] = None,
                as_of: Optional[str] = None, occurred_from: Optional[str] = None,
                occurred_to: Optional[str] = None, sort: Optional[Literal["rank", "chronological"]] = None,
                ontology: Optional[dict[str, str]] = None, format: Literal["json", "text"] = "json",
                max_tokens: Optional[int] = None) -> ContextResponse:
        options = dict(locals())
        del options["self"]
        return cast(ContextResponse, self._call("context", options))

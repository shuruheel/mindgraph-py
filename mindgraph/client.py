"""MindGraph Python client for the MindGraph Cloud API."""

from __future__ import annotations

import time
from typing import Any

import httpx


class MindGraphError(Exception):
    def __init__(self, message: str, status: int, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class MindGraph:
    """Client for the MindGraph REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        jwt: str | None = None,
        org_id: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        if org_id:
            headers["X-MindGraph-Org"] = org_id
        self._client = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MindGraph:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ---- HTTP helpers ----

    def _request(self, method: str, path: str, json: Any = None) -> Any:
        last_error: MindGraphError | None = None
        for attempt in range(self._max_retries + 1):
            resp = self._client.request(method, path, json=json)
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                err = MindGraphError(
                    f"{method} {path} failed: {resp.status_code}",
                    resp.status_code,
                    body,
                )
                # Retry on 503 (server warming up) with exponential backoff
                if resp.status_code == 503 and attempt < self._max_retries:
                    last_error = err
                    time.sleep(self._retry_backoff * (2**attempt))
                    continue
                raise err
            if not resp.content:
                return None
            return resp.json()
        raise last_error  # type: ignore[misc]

    # ---- Health ----

    def health(self) -> dict[str, str]:
        return self._request("GET", "/health")

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/stats")

    def schema_fill_stats(
        self, *, sample: int | None = None, layer: str | None = None
    ) -> Any:
        """Schema fill-rate report (measure-first tiering): per live node
        type, exact live count + sampled per-field fill rates; fields under
        5% flagged near-empty. ``sample`` caps per-type sampling (default
        1000); ``layer`` restricts (e.g. "epistemic")."""
        qs = "&".join(
            f"{k}={v}"
            for k, v in (("sample", sample), ("layer", layer))
            if v is not None
        )
        return self._request("GET", f"/stats/schema-fill{'?' + qs if qs else ''}")

    # ---- Reality Layer ----

    def capture(self, **kwargs: Any) -> Any:
        return self._request("POST", "/reality/capture", kwargs)

    def entity(self, **kwargs: Any) -> Any:
        return self._request("POST", "/reality/entity", kwargs)

    def find_or_create_entity(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "action": "create",
            "label": label,
            "props": {"entity_type": "other", **(props or {})},
        }
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/reality/entity", body)

    def find_or_create_person(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find a Person entity. Sets ``entity_type`` to ``"person"``."""
        merged = {"entity_type": "person", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def find_or_create_organization(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find an Organization entity. Sets ``entity_type`` to ``"organization"``."""
        merged = {"entity_type": "organization", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def find_or_create_nation(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find a Nation entity. Sets ``entity_type`` to ``"nation"``."""
        merged = {"entity_type": "nation", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def find_or_create_event(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find an Event entity. Sets ``entity_type`` to ``"event"``."""
        merged = {"entity_type": "event", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def find_or_create_place(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find a Place entity. Sets ``entity_type`` to ``"place"``."""
        merged = {"entity_type": "place", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def find_or_create_concept(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or find a Concept entity. Sets ``entity_type`` to ``"concept"``."""
        merged = {"entity_type": "concept", **(props or {})}
        return self.find_or_create_entity(label, merged, agent_id)

    def add_observation(
        self,
        label: str,
        description: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture an observation via the Reality layer.

        Posts to ``/reality/capture`` with action ``observation``.
        """
        body: dict[str, Any] = {
            "action": "observation",
            "label": label,
            "summary": description,
        }
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/reality/capture", body)

    def resolve_entity(
        self,
        text: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve *text* to an existing entity via alias matching.

        Returns ``{"uid": "<uid>"}`` or ``{"uid": null}`` if no match.
        """
        body: dict[str, Any] = {"action": "resolve", "text": text}
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/reality/entity", body)

    def fuzzy_resolve_entity(
        self,
        text: str,
        limit: int = 5,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Fuzzy-match *text* against existing entities.

        Returns ``{"matches": [{"uid", "label", "score"}, ...]}``.
        """
        body: dict[str, Any] = {"action": "fuzzy_resolve", "text": text, "limit": limit}
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/reality/entity", body)

    # ---- Epistemic Layer ----

    def argue(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/argument", kwargs)

    def inquire(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/inquiry", kwargs)

    def structure(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/structure", kwargs)

    def add_claim(
        self,
        label: str,
        content: str,
        confidence: float | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a claim (hypothesis) via the Epistemic layer.

        Posts to ``/epistemic/inquiry`` with action ``hypothesis``.
        """
        body: dict[str, Any] = {
            "action": "hypothesis",
            "label": label,
            "summary": content,
        }
        if confidence is not None:
            body["confidence"] = confidence
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/epistemic/inquiry", body)

    def add_evidence(
        self,
        label: str,
        description: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Add evidence via the Epistemic argument endpoint.

        Posts to ``/epistemic/argument`` with an evidence object.
        """
        body: dict[str, Any] = {
            "evidence": {
                "label": label,
                "summary": description,
            },
        }
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/epistemic/argument", body)

    # ---- Intent Layer ----

    def commit(self, **kwargs: Any) -> Any:
        return self._request("POST", "/intent/commitment", kwargs)

    def deliberate(self, **kwargs: Any) -> Any:
        return self._request("POST", "/intent/deliberation", kwargs)

    def open_decision(
        self,
        label: str,
        *,
        summary: str | None = None,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Open a new decision for deliberation. Returns the Decision node."""
        body: dict[str, Any] = {"action": "open_decision", "label": label}
        if summary:
            body["summary"] = summary
        if props:
            body["props"] = props
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/intent/deliberation", body)

    def add_option(
        self,
        decision_uid: str,
        label: str,
        *,
        summary: str | None = None,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Add an option to an open decision. Returns the Option node."""
        body: dict[str, Any] = {
            "action": "add_option",
            "decision_uid": decision_uid,
            "label": label,
        }
        if summary:
            body["summary"] = summary
        if props:
            body["props"] = props
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/intent/deliberation", body)

    def resolve_decision(
        self,
        decision_uid: str,
        chosen_option_uid: str,
        *,
        summary: str | None = None,
        props: dict[str, Any] | None = None,
        informs_uid: list[str] | None = None,
        as_of_date: str | None = None,
        session_id: str | None = None,
        retrieval_trace_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a decision by choosing an option.

        *chosen_option_uid* must be the uid of an option previously added
        via :meth:`add_option`.
        """
        body: dict[str, Any] = {
            "action": "resolve",
            "decision_uid": decision_uid,
            "chosen_option_uid": chosen_option_uid,
        }
        if summary:
            body["summary"] = summary
        if props:
            body["props"] = props
        if informs_uid:
            body["informs_uid"] = informs_uid
        if as_of_date:
            body["as_of_date"] = as_of_date
        if session_id:
            body["session_id"] = session_id
        if retrieval_trace_id:
            body["retrieval_trace_id"] = retrieval_trace_id
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/intent/deliberation", body)

    # ---- Action Layer ----

    def procedure(self, **kwargs: Any) -> Any:
        return self._request("POST", "/action/procedure", kwargs)

    def risk(self, **kwargs: Any) -> Any:
        return self._request("POST", "/action/risk", kwargs)

    # ---- Memory Layer ----

    def session(self, **kwargs: Any) -> Any:
        return self._request("POST", "/memory/session", kwargs)

    def journal(
        self,
        label: str,
        props: dict[str, Any] | None = None,
        *,
        summary: str | None = None,
        session_uid: str | None = None,
        relevant_node_uids: list[str] | None = None,
        confidence: float | None = None,
        salience: float | None = None,
        agent_id: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {"action": "journal", "label": label}
        if props:
            body["props"] = props
        if summary:
            body["summary"] = summary
        if session_uid:
            body["session_uid"] = session_uid
        if relevant_node_uids:
            body["relevant_node_uids"] = relevant_node_uids
        if confidence is not None:
            body["confidence"] = confidence
        if salience is not None:
            body["salience"] = salience
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/memory/session", body)

    def distill(self, **kwargs: Any) -> Any:
        return self._request("POST", "/memory/distill", kwargs)

    def memory_config(self, **kwargs: Any) -> Any:
        return self._request("POST", "/memory/config", kwargs)

    # ---- Agent Layer ----

    def plan(self, **kwargs: Any) -> Any:
        return self._request("POST", "/agent/plan", kwargs)

    def governance(self, **kwargs: Any) -> Any:
        return self._request("POST", "/agent/governance", kwargs)

    def execution(self, **kwargs: Any) -> Any:
        return self._request("POST", "/agent/execution", kwargs)

    # ---- Cross-cutting ----

    def merge_candidates(self) -> list[dict[str, Any]]:
        """Pending merge candidates: suspected duplicate pairs recorded by the
        dedup pipeline's ambiguous zone, awaiting merge/dismiss (server >= 1.3).
        """
        return self._request("POST", "/retrieve", {"action": "merge_candidates"})

    def stale_derivations(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Derived statements awaiting repair after a load-bearing premise changed."""
        return self._request(
            "POST",
            "/retrieve",
            {"action": "stale_derivations", "limit": limit, "offset": offset},
        )

    def retrieve(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve nodes by action. Returns a list of results.

        Note: ``action="semantic"`` requires a configured embedding provider
        on the server. For semantic search, use :meth:`retrieve_context` instead.
        """
        return self._request("POST", "/retrieve", kwargs)

    def preferences(
        self,
        query: str | None = None,
        k: int = 10,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve the user's preferences (stated or learned).

        With *query*, returns topic-relevant preferences — the semantic leg
        bridges low lexical overlap, so ``"suggest a hotel"`` surfaces a
        stored ``"loved the rooftop pool"``. Without *query*, returns all
        preferences, most salient first. Either way the result is a list of
        search results (``{"node": ..., "score": ...}``); ``score`` is
        relevance with a query, salience without. Use this for
        advice/recommendation requests so answers reflect what the user likes.
        """
        body: dict[str, Any] = {"action": "preferences"}
        if query is not None:
            body["query"] = query
            body["k"] = k
        if limit is not None:
            body["limit"] = limit
        if offset is not None:
            body["offset"] = offset
        return self._request("POST", "/retrieve", body)

    def traverse(self, **kwargs: Any) -> Any:
        """POST /traverse. Steps in the response carry ``path_cost`` (sum of
        -ln(edge weight) along the selected cheapest path; lower = stronger) and
        ``path_confidence`` (product of edge confidences; a ranking signal,
        not a calibrated probability). ``depth`` is the hop count of that
        min-cost witness path, which may exceed the fewest-hop distance."""
        return self._request("POST", "/traverse", kwargs)

    def evolve(self, **kwargs: Any) -> Any:
        return self._request("POST", "/evolve", kwargs)

    # ---- Node CRUD ----

    def get_node(self, uid: str) -> dict[str, Any]:
        return self._request("GET", f"/node/{uid}")

    def add_node(
        self,
        label: str,
        node_type: str | None = None,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a node via the low-level CRUD endpoint.

        The server requires ``props["_type"]`` to determine the node variant.
        If *node_type* is provided and ``_type`` is not already in *props*,
        it is injected automatically.
        """
        body: dict[str, Any] = {"label": label}
        p = dict(props or {})
        if node_type and "_type" not in p:
            p["_type"] = node_type
        body["props"] = p
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/node", body)

    def update_node(self, uid: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/node/{uid}", kwargs)

    def delete_node(self, uid: str) -> None:
        self._request("DELETE", f"/node/{uid}")

    def batch_delete_nodes(
        self,
        uids: list[str] | None = None,
        agent_id: str | None = None,
        filter: dict[str, Any] | None = None,
        reason: str | None = None,
        by: str | None = None,
        hard_purge: bool = False,
    ) -> dict[str, Any]:
        """Batch tombstone-cascade nodes by UIDs, agent_id, and/or filter.

        Returns counts of nodes/edges tombstoned and purged.
        """
        body: dict[str, Any] = {"hard_purge": hard_purge}
        if uids:
            body["uids"] = uids
        if agent_id:
            body["agent_id"] = agent_id
        if filter:
            body["filter"] = filter
        if reason:
            body["reason"] = reason
        if by:
            body["by"] = by
        return self._request("POST", "/nodes/delete", body)

    def get_node_history(self, uid: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/node/{uid}/history")

    def get_node_at_version(self, uid: str, version: int) -> dict[str, Any]:
        return self._request("GET", f"/node/{uid}/history/{version}")

    # ---- Edge CRUD ----

    def add_link(
        self,
        from_uid: str,
        to_uid: str,
        edge_type: str,
        agent_id: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "from_uid": from_uid,
            "to_uid": to_uid,
            "edge_type": edge_type,
        }
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/link", body)

    def add_edge(
        self,
        from_uid: str,
        to_uid: str,
        edge_type: str,
        *,
        weight: float | None = None,
        props: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> Any:
        """Create an edge via the low-level CRUD endpoint.

        The server requires ``props["_type"]`` to determine the edge variant.
        If *edge_type* is provided and ``_type`` is not already in *props*,
        it is injected automatically.
        """
        body: dict[str, Any] = {
            "from_uid": from_uid,
            "to_uid": to_uid,
        }
        p = dict(props or {})
        if edge_type and "_type" not in p:
            p["_type"] = edge_type
        body["props"] = p
        if weight is not None:
            body["weight"] = weight
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/edge", body)

    def update_edge(self, uid: str, **kwargs: Any) -> Any:
        return self._request("PATCH", f"/edge/{uid}", kwargs)

    def delete_edge(self, uid: str) -> None:
        self._request("DELETE", f"/edge/{uid}")

    def get_edge_history(self, uid: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/edge/{uid}/history")

    def get_edges(
        self,
        from_uid: str | None = None,
        to_uid: str | None = None,
    ) -> list[dict[str, Any]]:
        """List edges filtered by source and/or target node.

        At least one of *from_uid* or *to_uid* is **required** — the server
        returns 400 if neither is provided.
        """
        if not from_uid and not to_uid:
            raise ValueError("at least one of from_uid or to_uid is required")
        params: dict[str, str] = {}
        if from_uid:
            params["from_uid"] = from_uid
        if to_uid:
            params["to_uid"] = to_uid
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/edges?{qs}")

    def get_edge_between(
        self,
        from_uid: str,
        to_uid: str,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"from_uid": from_uid, "to_uid": to_uid}
        if edge_type:
            params["edge_type"] = edge_type
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/edge/between?{qs}")

    # ---- Search ----

    def search(
        self,
        query: str,
        node_type: str | None = None,
        layer: str | None = None,
        limit: int | None = None,
        min_score: float | None = None,
        include_edges: bool = False,
        include_chunks: bool = False,
        *,
        project_uid: str | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Full-text search over nodes.

        When ``include_edges`` or ``include_chunks`` is True the response is an
        enriched dict with ``results``, ``edges``, and ``chunks`` keys.
        Otherwise a flat list of search results is returned.
        """
        body: dict[str, Any] = {"query": query}
        if project_uid:
            body["project_uid"] = project_uid
        if node_type:
            body["node_type"] = node_type
        if layer:
            body["layer"] = layer
        if limit:
            body["limit"] = limit
        if min_score is not None:
            body["min_score"] = min_score
        if include_edges:
            body["include_edges"] = True
        if include_chunks:
            body["include_chunks"] = True
        return self._request("POST", "/search", body)

    def hybrid_search(
        self,
        query: str,
        k: int | None = None,
        node_types: list[str] | None = None,
        layer: str | None = None,
        explain: bool = False,
        *,
        project_uid: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid BM25 + vector search with reciprocal rank fusion.

        With ``explain=True`` each result carries a ``legs`` list — the
        "why retrieved" detail: which legs (``fts``/``vec``) surfaced it,
        the 1-based within-leg rank the fusion used, and the leg's raw
        score. The fused ``score`` reconstructs as ``sum(1/(60 + rank))``.
        Requires server >= 1.2.0; older servers ignore the flag.
        """
        body: dict[str, Any] = {"action": "hybrid", "query": query}
        if project_uid:
            body["project_uid"] = project_uid
        if k:
            body["k"] = k
        if node_types:
            body["node_types"] = node_types
        if layer:
            body["layer"] = layer
        if explain:
            body["explain"] = True
        return self._request("POST", "/retrieve", body)

    # ---- Nodes listing ----

    def get_nodes(
        self,
        node_type: str | None = None,
        layer: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        params: dict[str, str] = {}
        if node_type:
            params["node_type"] = node_type
        if layer:
            params["layer"] = layer
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/nodes?{qs}")

    def get_agent_nodes(self, agent_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/agent/{agent_id}/nodes")

    # ---- Batch ----

    def batch(self, **kwargs: Any) -> Any:
        return self._request("POST", "/batch", kwargs)

    def get_nodes_batch(self, uids: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple nodes by UID in a single request."""
        return self._request("POST", "/nodes/batch", {"uids": uids})

    def get_edges_batch(self, uids: list[str]) -> list[dict[str, Any]]:
        """Fetch all edges between a set of node UIDs."""
        return self._request("POST", "/edges/batch", {"uids": uids})

    # ---- Embeddings ----

    def configure_embeddings(self, **kwargs: Any) -> Any:
        return self._request("POST", "/embeddings/configure", kwargs)

    def embedding_search(self, **kwargs: Any) -> Any:
        return self._request("POST", "/embeddings/search", kwargs)

    def embedding_search_text(self, **kwargs: Any) -> Any:
        return self._request("POST", "/embeddings/search-text", kwargs)

    def get_embedding(self, uid: str) -> Any:
        return self._request("GET", f"/node/{uid}/embedding")

    def set_embedding(self, uid: str, vector: list[float]) -> None:
        self._request("PUT", f"/node/{uid}/embedding", {"vector": vector})

    def delete_embedding(self, uid: str) -> None:
        self._request("DELETE", f"/node/{uid}/embedding")

    # ---- Entity resolution ----

    def merge_entities(
        self,
        keep_uid: str,
        merge_uid: str,
        agent_id: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {"keep_uid": keep_uid, "merge_uid": merge_uid}
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/entities/merge", body)

    def add_alias(
        self,
        text: str,
        canonical_uid: str,
        score: float | None = None,
    ) -> Any:
        body: dict[str, Any] = {"text": text, "canonical_uid": canonical_uid}
        if score is not None:
            body["score"] = score
        return self._request("POST", "/alias", body)

    def get_aliases(self, uid: str) -> Any:
        return self._request("GET", f"/aliases/{uid}")

    def resolve_alias(self, text: str) -> Any:
        from urllib.parse import quote

        return self._request("GET", f"/resolve?text={quote(text)}")

    # ---- Export / Import ----

    def export_graph(self) -> Any:
        return self._request("GET", "/export")

    def export_provenance(self, document_uid: str) -> Any:
        """One document's extraction provenance as JSON-LD (PROV-O + CiTO +
        W3C Web Annotation anchors). Positions are chunk-relative UTF-8 byte
        offsets (``mg:offsetUnit``)."""
        from urllib.parse import quote

        return self._request(
            "GET", f"/export/prov?document_uid={quote(document_uid, safe='')}"
        )

    def import_graph(self, data: Any) -> Any:
        return self._request("POST", "/import", data)

    # ---- Lifecycle ----

    def decay(
        self,
        half_life_secs: float,
        min_salience: float | None = None,
        min_age_secs: float | None = None,
    ) -> Any:
        body: dict[str, Any] = {"half_life_secs": half_life_secs}
        if min_salience is not None:
            body["min_salience"] = min_salience
        if min_age_secs is not None:
            body["min_age_secs"] = min_age_secs
        return self._request("POST", "/decay", body)

    def purge(self, before: float | None = None) -> Any:
        body: dict[str, Any] = {}
        if before is not None:
            body["before"] = before
        return self._request("POST", "/purge", body)

    # ---- Epistemic queries ----

    def get_goals(self) -> list[dict[str, Any]]:
        return self._request("GET", "/goals")

    def get_open_decisions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/decisions")

    def get_open_questions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/questions")

    def get_weak_claims(self) -> list[dict[str, Any]]:
        return self._request("GET", "/claims/weak")

    def get_contradictions(self) -> list[Any]:
        return self._request("GET", "/contradictions")

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        return self._request("GET", "/approvals/pending")

    # ---- Traversal shortcuts ----

    def reasoning_chain(self, uid: str, max_depth: int = 5) -> list[dict[str, Any]]:
        r = self._request(
            "POST",
            "/traverse",
            {"action": "chain", "start_uid": uid, "max_depth": max_depth},
        )
        return r.get("steps", []) if isinstance(r, dict) else r

    def neighborhood(self, uid: str, max_depth: int = 1) -> list[dict[str, Any]]:
        r = self._request(
            "POST",
            "/traverse",
            {"action": "neighborhood", "start_uid": uid, "max_depth": max_depth},
        )
        return r.get("steps", []) if isinstance(r, dict) else r

    def subgraph(
        self,
        uid: str,
        max_depth: int | None = None,
        direction: str | None = None,
        edge_types: list[str] | None = None,
        weight_threshold: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"start_uids": [uid]}
        if max_depth is not None:
            body["max_depth"] = max_depth
        if direction:
            body["direction"] = direction
        if edge_types:
            body["edge_types"] = edge_types
        if weight_threshold is not None:
            body["weight_threshold"] = weight_threshold
        return self._request("POST", "/subgraph", body)

    # ---- Lifecycle shortcuts ----

    def tombstone(
        self, uid: str, reason: str | None = None, agent_id: str | None = None
    ) -> Any:
        body: dict[str, Any] = {"action": "tombstone", "uid": uid}
        if reason:
            body["reason"] = reason
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/evolve", body)

    def restore(self, uid: str, agent_id: str | None = None) -> Any:
        body: dict[str, Any] = {"action": "restore", "uid": uid}
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/evolve", body)

    # ---- Ingestion & Retrieval ----

    def ingest_chunk(
        self,
        content: str,
        *,
        chunk_type: str | None = None,
        document_uid: str | None = None,
        chunk_index: int | None = None,
        label: str | None = None,
        layers: list[str] | None = None,
        agent_id: str | None = None,
        ontology_schema_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if chunk_type:
            body["chunk_type"] = chunk_type
        if document_uid:
            body["document_uid"] = document_uid
        if chunk_index is not None:
            body["chunk_index"] = chunk_index
        if label:
            body["label"] = label
        if layers:
            body["layers"] = layers
        if agent_id:
            body["agent_id"] = agent_id
        if ontology_schema_id:
            body["ontology_schema_id"] = ontology_schema_id
        return self._request("POST", "/ingest/chunk", body)

    def ingest_document(
        self,
        content: str,
        *,
        title: str | None = None,
        project_uid: str | None = None,
        document_type: str | None = None,
        content_type: str | None = None,
        source_uri: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: float | None = None,
        layers: list[str] | None = None,
        agent_id: str | None = None,
        # Paper metadata
        authors: list[str] | None = None,
        abstract_text: str | None = None,
        doi: str | None = None,
        publication_date: str | None = None,
        journal: str | None = None,
        keywords: list[str] | None = None,
        citation_count: int | None = None,
        arxiv_id: str | None = None,
        language: str | None = None,
        page_offsets: list[dict[str, Any]] | None = None,
        page_count: int | None = None,
        mime_type: str | None = None,
        force_reingest: bool | None = None,
        ontology_schema_id: str | None = None,
        participants: list[dict[str, Any]] | None = None,
        occurred_at: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if title:
            body["title"] = title
        if project_uid:
            body["project_uid"] = project_uid
        if document_type:
            body["document_type"] = document_type
        if content_type:
            body["content_type"] = content_type
        if source_uri:
            body["source_uri"] = source_uri
        if chunk_size is not None:
            body["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            body["chunk_overlap"] = chunk_overlap
        if layers:
            body["layers"] = layers
        if agent_id:
            body["agent_id"] = agent_id
        if authors:
            body["authors"] = authors
        if abstract_text:
            body["abstract_text"] = abstract_text
        if doi:
            body["doi"] = doi
        if publication_date:
            body["publication_date"] = publication_date
        if journal:
            body["journal"] = journal
        if keywords:
            body["keywords"] = keywords
        if citation_count is not None:
            body["citation_count"] = citation_count
        if arxiv_id:
            body["arxiv_id"] = arxiv_id
        if language:
            body["language"] = language
        if page_offsets:
            # Each entry is {"page": int (1-based), "char_start": int}, where
            # char_start is a UTF-8 BYTE offset into `content` (not a codepoint
            # count) — use len(s.encode("utf-8")), or pages drift on non-ASCII text.
            body["page_offsets"] = page_offsets
        if page_count is not None:
            body["page_count"] = page_count
        if mime_type:
            body["mime_type"] = mime_type
        if force_reingest is not None:
            body["force_reingest"] = force_reingest
        if ontology_schema_id:
            body["ontology_schema_id"] = ontology_schema_id
        if participants:
            # Each entry is {"name": str, "organization": str|None, "role": str|None}.
            body["participants"] = participants
        if occurred_at:
            body["occurred_at"] = occurred_at
        if context:
            body["context"] = context
        return self._request("POST", "/ingest/document", body)

    def ingest_session(
        self,
        content: str,
        *,
        title: str | None = None,
        session_uid: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: float | None = None,
        layers: list[str] | None = None,
        agent_id: str | None = None,
        ontology_schema_id: str | None = None,
        participants: list[dict[str, Any]] | None = None,
        occurred_at: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if title:
            body["title"] = title
        if session_uid:
            body["session_uid"] = session_uid
        if chunk_size is not None:
            body["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            body["chunk_overlap"] = chunk_overlap
        if layers:
            body["layers"] = layers
        if agent_id:
            body["agent_id"] = agent_id
        if ontology_schema_id:
            body["ontology_schema_id"] = ontology_schema_id
        if participants:
            body["participants"] = participants
        if occurred_at:
            body["occurred_at"] = occurred_at
        if context:
            body["context"] = context
        return self._request("POST", "/ingest/session", body)

    def retrieve_context(
        self,
        query: str,
        *,
        project_uid: str | None = None,
        node_limit: int | None = None,
        article_limit: int | None = None,
        chunk_limit: int | None = None,
        node_types: list[str] | None = None,
        layer: str | None = None,
        include_graph: bool | None = None,
        min_similarity: float | None = None,
        graph_expansion_limit: int | None = None,
        graph_max_depth: int | None = None,
        valid_at: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve context from the knowledge graph.

        Returns articles (synthesized wiki summaries), graph nodes with
        source_documents provenance, and optionally raw chunks.

        Each graph node may also carry an optional ``source_chunks`` array of
        citation-provenance spans. Each entry is a dict with keys:
        ``chunk_uid`` (str), ``char_start``/``char_end`` (int|None, UTF-8 byte
        offsets into the chunk), ``page_start``/``page_end`` (int|None, 1-based
        page numbers, None if no page map), ``quote`` (str|None, the verbatim
        source span when matched), and ``anchor`` (str|None, a JSON-encoded
        Web-Annotation selector string).

        Claim nodes may additionally carry an optional ``believed_by`` array of
        per-agent stances. Each entry is a dict with keys: ``agent_uid`` (str),
        ``agent_label`` (str), and ``confidence`` (float|None, the asserting
        agent's certainty, None if unspecified).

        Args:
            query: Natural language search query.
            project_uid: Corpus Project whose member sources define retrieval.
            node_limit: Max graph nodes (default 10).
            article_limit: Max wiki articles (default 3). Set 0 to skip.
            chunk_limit: Max raw chunks (default 0). Set >0 to include source text.
            node_types: Filter to specific node types.
            layer: Filter to a specific layer.
            include_graph: Include graph nodes and edges (default True).
            min_similarity: Minimum similarity threshold.
            graph_expansion_limit: Reserve up to this many node slots for
                cheapest-first graph expansion (default 0, direct-only).
            graph_max_depth: Maximum graph-expansion hops (default 2).
            valid_at: ISO-8601 date used to annotate temporal validity.
        """
        body: dict[str, Any] = {"query": query}
        if project_uid:
            body["project_uid"] = project_uid
        if node_limit is not None:
            body["node_limit"] = node_limit
        if article_limit is not None:
            body["article_limit"] = article_limit
        if chunk_limit is not None:
            body["chunk_limit"] = chunk_limit
        if node_types:
            body["node_types"] = node_types
        if layer:
            body["layer"] = layer
        if include_graph is not None:
            body["include_graph"] = include_graph
        if min_similarity is not None:
            body["min_similarity"] = min_similarity
        if graph_expansion_limit is not None:
            body["graph_expansion_limit"] = graph_expansion_limit
        if graph_max_depth is not None:
            body["graph_max_depth"] = graph_max_depth
        if valid_at is not None:
            body["valid_at"] = valid_at
        return self._request("POST", "/retrieve/context", body)

    def backfill_node_sources(self) -> dict[str, Any]:
        """Backfill node_source provenance from existing ExtractedFrom edges."""
        return self._request("POST", "/backfill/node-sources", {})

    def backfill_anchors(self) -> dict[str, Any]:
        """Backfill citation anchors (source_chunks spans) for existing graphs.

        Returns a background job descriptor (e.g. ``{"job_id": ...}``).
        """
        return self._request("POST", "/backfill/anchors", {})

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/jobs")

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/jobs/{job_id}")

    def cancel_job(self, job_id: str) -> Any:
        return self._request("POST", f"/jobs/{job_id}/cancel")

    def resume_document(
        self,
        doc_uid: str,
        *,
        layers: list[str] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Resume ingestion of a document that has failed chunks."""
        body: dict[str, Any] = {}
        if layers:
            body["layers"] = layers
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", f"/ingest/resume/{doc_uid}", body)

    def delete_document(self, uid: str) -> Any:
        """Delete a document and all its chunks and extracted nodes."""
        return self._request("DELETE", f"/ingest/document/{uid}")

    def cleanup_orphans(self) -> Any:
        return self._request("POST", "/ingest/cleanup")

    def embed_all(self) -> Any:
        return self._request("POST", "/ingest/embed-all")

    def clear_graph(self) -> dict[str, Any]:
        return self._request("POST", "/clear")

    # ── Wiki ──────────────────────────────────────────────────────────────

    def list_articles(
        self,
        *,
        article_type: str | None = None,
        covers_node_type: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List wiki articles with optional filters."""
        params: dict[str, str] = {}
        if article_type:
            params["article_type"] = article_type
        if covers_node_type:
            params["covers_node_type"] = covers_node_type
        if search:
            params["search"] = search
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/wiki/articles?{qs}" if qs else "/wiki/articles")

    def get_article(self, uid: str) -> dict[str, Any]:
        """Get a single wiki article by UID."""
        return self._request("GET", f"/wiki/article/{uid}")

    def get_article_by_subject(self, subject_uid: str) -> dict[str, Any] | None:
        """Find the article that covers or summarizes a given entity/document UID."""
        try:
            return self._request("GET", f"/wiki/article/by-subject/{subject_uid}")
        except MindGraphError as e:
            if e.status == 404:
                return None
            raise

    def update_article(self, uid: str, content: str) -> dict[str, Any]:
        """Update an article's markdown content (user editing)."""
        return self._request("PATCH", f"/wiki/article/{uid}", {"content": content})

    def compile_document(self, doc_uid: str) -> dict[str, Any]:
        """Trigger wiki compilation for a specific document."""
        return self._request("POST", f"/wiki/compile/{doc_uid}")

    def compile_entity(self, entity_uid: str) -> dict[str, Any]:
        """Trigger wiki compilation for a specific entity."""
        return self._request("POST", f"/wiki/compile/entity/{entity_uid}")

    def compile_all(self) -> dict[str, Any]:
        """Backfill: compile articles for all documents and eligible entities."""
        return self._request("POST", "/wiki/compile/all")

    # ---- Synthesis (Projects) ----

    def signals(
        self,
        project_uid: str,
        *,
        signals: str | None = None,
        target_types: str | None = None,
    ) -> dict[str, Any]:
        """Mine cross-document structural signals for a project's corpus.

        Returns entity bridges, claim hubs, ranked/clustered claim hubs,
        theory support gaps, concept clusters, analogy candidates, and
        dialectical pairs. Blocking; no LLM calls.

        Args:
            project_uid: UID of the Project node.
            signals: Comma-separated subset of signal names to compute
                (e.g. ``"clustered_claim_hubs,dialectical_pairs"``). If
                omitted, all signals run.
            target_types: Comma-separated node types filter for
                ``entity_bridges`` and ``claim_hubs``.
        """
        params: dict[str, str] = {}
        if signals is not None:
            params["signals"] = signals
        if target_types is not None:
            params["target_types"] = target_types
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"/synthesis/signals/{project_uid}"
        if qs:
            path = f"{path}?{qs}"
        return self._request("GET", path)

    def run_synthesis(self, project_uid: str) -> dict[str, Any]:
        """Spawn a background synthesis job for a project.

        Mines signals, selects top idea clusters, runs LLM synthesis,
        and persists candidate Article nodes linked via ``Covers`` edges.

        Returns ``{"job_id": str}``; poll with :meth:`get_job`.
        """
        return self._request("POST", f"/synthesis/run/{project_uid}")

    # ========================================================================
    # Operational Ontology Layer (Layer 7)
    # ========================================================================

    # ---- Schema management (cloud Postgres) ----

    def list_ontology_schemas(self) -> dict[str, Any]:
        """List ontology schemas for the authenticated org."""
        return self._request("GET", "/v1/ontology/schemas")

    def get_ontology_schema(self, schema_id: str) -> dict[str, Any]:
        """Get one schema with its object types + relation types."""
        return self._request("GET", f"/v1/ontology/schemas/{schema_id}")

    def create_ontology_schema(
        self, *, name: str, description: str | None = None
    ) -> dict[str, Any]:
        """Create a draft schema."""
        body: dict[str, Any] = {"name": name}
        if description is not None:
            body["description"] = description
        return self._request("POST", "/v1/ontology/schemas", body)

    def update_ontology_schema(self, schema_id: str, **kwargs: Any) -> dict[str, Any]:
        """Update a draft schema's name or description."""
        return self._request("PATCH", f"/v1/ontology/schemas/{schema_id}", kwargs)

    def activate_ontology_schema(self, schema_id: str) -> dict[str, Any]:
        """Mark a draft schema active. Auto-deprecates the previous active schema."""
        return self._request("POST", f"/v1/ontology/schemas/{schema_id}/activate")

    def deprecate_ontology_schema(self, schema_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/ontology/schemas/{schema_id}/deprecate")

    def archive_ontology_schema(self, schema_id: str) -> dict[str, Any]:
        """Soft-delete (archive) a schema."""
        return self._request("DELETE", f"/v1/ontology/schemas/{schema_id}")

    def propose_ontology_schema(self, **kwargs: Any) -> dict[str, Any]:
        """Kick off an LLM-driven schema proposal.

        Returns ``{"schema_id": str, "job_id": str}`` immediately; poll
        ``get_ontology_schema(schema_id)`` for progressive state.

        Recognized kwargs: description, template_hint, source_uids,
        source_documents, target_use_case, example_objects, example_queries,
        desired_workflows, parent_schema_id.
        """
        return self._request("POST", "/v1/ontology/propose-schema", kwargs)

    def test_ontology_schema(
        self, schema_id: str, *, example_queries: list[str] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if example_queries is not None:
            body["example_queries"] = example_queries
        return self._request("POST", f"/v1/ontology/schemas/{schema_id}/test", body)

    # ---- Sub-resources ----

    def add_ontology_object_type(self, schema_id: str, **kwargs: Any) -> dict[str, Any]:
        """Create an object type on a schema.

        Recognized kwargs: name (required), display_name, description, fields,
        required_fields, identity_fields, aliases, examples, extraction_hints,
        default_confidence, review_policy, backing.

        `backing` binds the type to an external source (the semantic-contract
        mapping). Omit it for extracted/authored types. SQL example::

            backing={
                "kind": "sql",
                "sources": [{
                    "connection_ref": "conn_1",
                    "table": "customers",
                    "key": "id",
                    "field_map": {"name": {"column": "full_name", "mode": "indexed"}},
                }],
                "primary_key": "id",
                "title_field": "name",
                "sync": {"mode": "incremental", "cursor_column": "updated_at"},
            }
        """
        return self._request(
            "POST", f"/v1/ontology/schemas/{schema_id}/object-types", kwargs
        )

    def update_ontology_object_type(
        self, schema_id: str, type_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/v1/ontology/schemas/{schema_id}/object-types/{type_id}",
            kwargs,
        )

    def delete_ontology_object_type(
        self, schema_id: str, type_id: str
    ) -> dict[str, Any]:
        return self._request(
            "DELETE",
            f"/v1/ontology/schemas/{schema_id}/object-types/{type_id}",
        )

    def add_ontology_relation_type(
        self, schema_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request(
            "POST", f"/v1/ontology/schemas/{schema_id}/relation-types", kwargs
        )

    def update_ontology_relation_type(
        self, schema_id: str, type_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/v1/ontology/schemas/{schema_id}/relation-types/{type_id}",
            kwargs,
        )

    def delete_ontology_relation_type(
        self, schema_id: str, type_id: str
    ) -> dict[str, Any]:
        return self._request(
            "DELETE",
            f"/v1/ontology/schemas/{schema_id}/relation-types/{type_id}",
        )

    def analyze_ontology_semantic_guidance(self, schema_id: str) -> dict[str, Any]:
        """Generate inert semantic classifications for individual human review."""
        return self._request(
            "POST",
            f"/v1/ontology/schemas/{schema_id}/semantic-guidance/analyze",
            {},
        )

    def audit_ontology_duplicates(self, schema_id: str) -> dict[str, Any]:
        """Run a read-only exact-identity collision audit; never merge graph data."""
        return self._request(
            "POST", f"/v1/ontology/schemas/{schema_id}/duplicates/audit", {}
        )

    # ---- Proposals ----

    def list_ontology_proposals(
        self,
        *,
        status: str | None = None,
        schema_id: str | None = None,
        object_type: str | None = None,
        proposal_type: str | None = None,
        extract_job_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if schema_id is not None:
            params["schema_id"] = schema_id
        if object_type is not None:
            params["object_type"] = object_type
        if proposal_type is not None:
            params["proposal_type"] = proposal_type
        if extract_job_id is not None:
            params["extract_job_id"] = extract_job_id
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        path = "/v1/ontology/proposals"
        if qs:
            path = f"{path}?{qs}"
        return self._request("GET", path)

    def get_ontology_proposal(self, proposal_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/ontology/proposals/{proposal_id}")

    def patch_ontology_proposal(
        self, proposal_id: str, *, edits: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PATCH", f"/v1/ontology/proposals/{proposal_id}", {"edits": edits}
        )

    def approve_ontology_proposal(
        self,
        proposal_id: str,
        *,
        feedback: str | None = None,
        edits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if feedback is not None:
            body["feedback"] = feedback
        if edits is not None:
            body["edits"] = edits
        return self._request(
            "POST", f"/v1/ontology/proposals/{proposal_id}/approve", body
        )

    def reject_ontology_proposal(
        self, proposal_id: str, reason: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if reason is not None:
            body["reason"] = reason
        return self._request(
            "POST", f"/v1/ontology/proposals/{proposal_id}/reject", body
        )

    def apply_ontology_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Force-apply an approved proposal (idempotent retry for a stuck row)."""
        return self._request("POST", f"/v1/ontology/proposals/{proposal_id}/apply")

    def batch_approve_ontology_proposals(
        self, ids: list[str], feedback: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"ids": ids}
        if feedback is not None:
            body["feedback"] = feedback
        return self._request("POST", "/v1/ontology/proposals/batch-approve", body)

    def batch_reject_ontology_proposals(
        self, ids: list[str], reason: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"ids": ids}
        if reason is not None:
            body["reason"] = reason
        return self._request("POST", "/v1/ontology/proposals/batch-reject", body)

    def list_ontology_tools(self) -> dict[str, Any]:
        """Read-only agent tool manifest for the org's active ontology schema(s).

        Returns ``{"tools": [...]}`` — per active object type, descriptors for
        ``search_<objs>`` / ``get_<obj>`` / ``summarize_<obj>`` that an MCP
        server (or your own agent loop) renders into tools and dispatches into
        the ``/ontology`` read endpoints. ``summarize_<obj>`` returns the object
        — whether mapped from a connected SQL database or extracted from
        documents — plus its cognitive context (claims, risks, decisions).
        """
        return self._request("GET", "/v1/ontology/tools")

    # ---- Retrieval (graph server) ----

    def query_ontology(
        self, *, query: str, schema_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "schema_id": schema_id}
        body.update(kwargs)
        return self._request("POST", "/ontology/query", body)

    def get_domain_object(self, uid: str) -> dict[str, Any]:
        return self._request("GET", f"/ontology/object/{uid}")

    def get_domain_object_context(self, uid: str, *, depth: int = 2) -> dict[str, Any]:
        return self._request("GET", f"/ontology/object/{uid}/context?depth={depth}")

    def get_domain_object_history(self, uid: str) -> dict[str, Any]:
        return self._request("GET", f"/ontology/object/{uid}/history")

    def list_domain_objects(
        self,
        *,
        schema_id: str,
        object_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"schema_id": schema_id}
        if object_type is not None:
            params["object_type"] = object_type
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if sort is not None:
            params["sort"] = sort
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/ontology/objects?{qs}")

    def search_domain_objects(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Hybrid (FTS + semantic) search over domain objects.

        Recognized kwargs: schema_id, object_types, limit.
        Returns ``{"items": [{"object": ..., "score": float}]}``.
        """
        body: dict[str, Any] = {"query": query}
        body.update(kwargs)
        return self._request("POST", "/ontology/objects/search", body)

    def link_domain_objects(
        self,
        *,
        from_uid: str,
        to_uid: str,
        relation_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "action": "create",
            "from_uid": from_uid,
            "to_uid": to_uid,
            "relation_type": relation_type,
        }
        body.update(kwargs)
        return self._request("POST", "/ontology/relation", body)

    def ontology_stats(
        self, schema_id: str, sample: int | None = None
    ) -> dict[str, Any]:
        """Per-object-type coverage stats for a schema (C2f): field fill rates
        (with a ``near_empty`` flag below 5%) and identity collisions, over a
        bounded per-type sample (default 500, max 2000).
        """
        qs = f"schema_id={schema_id}"
        if sample is not None:
            qs += f"&sample={sample}"
        return self._request("GET", f"/ontology/stats?{qs}")

    def create_domain_object(
        self,
        *,
        schema_id: str,
        object_type: str,
        canonical_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a domain object by hand (auto-approved).

        Returns ``{"uid": ..., "proposal_id": ...}``. Raises on 409 if an
        object of the same type + canonical_name already exists, unless
        ``allow_duplicate=True`` is passed. Extra kwargs (``fields``,
        ``aliases``, ``identity``, ``confidence``) pass through.
        """
        body: dict[str, Any] = {
            "schema_id": schema_id,
            "object_type": object_type,
            "canonical_name": canonical_name,
        }
        body.update(kwargs)
        return self._request("POST", "/v1/ontology/objects", body)

    # ---- Extraction ----

    def extract_ontology(
        self,
        *,
        ontology_schema_id: str,
        source_uids: list[str],
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Batch-extract ontology objects from existing documents/chunks.

        ``mode`` is one of ``"propose_only"``, ``"respect_policies"`` (server
        default), or ``"force_auto_apply"``. Omit to let the server pick.
        """
        body: dict[str, Any] = {
            "ontology_schema_id": ontology_schema_id,
            "source_uids": source_uids,
        }
        if mode is not None:
            body["mode"] = mode
        return self._request("POST", "/ontology/extract", body)

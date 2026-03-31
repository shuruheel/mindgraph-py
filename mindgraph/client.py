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

    def retrieve(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Retrieve nodes by action. Returns a list of results.

        Note: ``action="semantic"`` requires a configured embedding provider
        on the server. For semantic search, use :meth:`retrieve_context` instead.
        """
        return self._request("POST", "/retrieve", kwargs)

    def traverse(self, **kwargs: Any) -> Any:
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

    def update_node(
        self, uid: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request("PATCH", f"/node/{uid}", kwargs)

    def delete_node(self, uid: str) -> None:
        self._request("DELETE", f"/node/{uid}")

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
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"query": query}
        if node_type:
            body["node_type"] = node_type
        if layer:
            body["layer"] = layer
        if limit:
            body["limit"] = limit
        return self._request("POST", "/search", body)

    def hybrid_search(
        self,
        query: str,
        k: int | None = None,
        node_types: list[str] | None = None,
        layer: str | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"action": "hybrid", "query": query}
        if k:
            body["k"] = k
        if node_types:
            body["node_types"] = node_types
        if layer:
            body["layer"] = layer
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
            "POST", "/traverse", {"action": "chain", "start_uid": uid, "max_depth": max_depth}
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
        return self._request("POST", "/ingest/chunk", body)

    def ingest_document(
        self,
        content: str,
        *,
        title: str | None = None,
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
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if title:
            body["title"] = title
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
        return self._request("POST", "/ingest/session", body)

    def retrieve_context(
        self,
        query: str,
        *,
        k: int | None = None,
        depth: int | None = None,
        node_types: list[str] | None = None,
        layer: str | None = None,
        include_chunks: bool | None = None,
        include_graph: bool | None = None,
        min_similarity: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if k is not None:
            body["k"] = k
        if depth is not None:
            body["depth"] = depth
        if node_types:
            body["node_types"] = node_types
        if layer:
            body["layer"] = layer
        if include_chunks is not None:
            body["include_chunks"] = include_chunks
        if include_graph is not None:
            body["include_graph"] = include_graph
        if min_similarity is not None:
            body["min_similarity"] = min_similarity
        return self._request("POST", "/retrieve/context", body)

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


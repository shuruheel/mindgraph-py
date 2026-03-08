"""MindGraph Python client for the MindGraph Cloud API."""

from __future__ import annotations

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
    ):
        self.base_url = base_url.rstrip("/")
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
        resp = self._client.request(method, path, json=json)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise MindGraphError(
                f"{method} {path} failed: {resp.status_code}",
                resp.status_code,
                body,
            )
        if not resp.content:
            return None
        return resp.json()

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

    # ---- Epistemic Layer ----

    def argue(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/argument", kwargs)

    def inquire(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/inquiry", kwargs)

    def structure(self, **kwargs: Any) -> Any:
        return self._request("POST", "/epistemic/structure", kwargs)

    # ---- Intent Layer ----

    def commit(self, **kwargs: Any) -> Any:
        return self._request("POST", "/intent/commitment", kwargs)

    def deliberate(self, **kwargs: Any) -> Any:
        return self._request("POST", "/intent/deliberation", kwargs)

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

    def retrieve(self, **kwargs: Any) -> Any:
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
        body: dict[str, Any] = {"label": label}
        if node_type:
            body["node_type"] = node_type
        if props:
            body["props"] = props
        if agent_id:
            body["agent_id"] = agent_id
        return self._request("POST", "/node", body)

    def update_node(
        self, uid: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request("PATCH", f"/node/{uid}", kwargs)

    def delete_node(self, uid: str) -> None:
        self._request("DELETE", f"/node/{uid}")

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

    def get_edges(
        self,
        from_uid: str | None = None,
        to_uid: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if from_uid:
            params["from_uid"] = from_uid
        if to_uid:
            params["to_uid"] = to_uid
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self._request("GET", f"/edges?{qs}")

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

    # ---- Management (Cloud only) ----

    def signup(self, email: str, password: str) -> Any:
        return self._request("POST", "/v1/auth/signup", {"email": email, "password": password})

    def login(self, email: str, password: str) -> Any:
        return self._request("POST", "/v1/auth/login", {"email": email, "password": password})

    def create_api_key(self, name: str = "default") -> dict[str, Any]:
        return self._request("POST", "/v1/api-keys", {"name": name})

    def list_api_keys(self) -> dict[str, Any]:
        return self._request("GET", "/v1/api-keys")

    def revoke_api_key(self, key_id: str) -> None:
        self._request("DELETE", f"/v1/api-keys/{key_id}")

    def get_usage(self) -> Any:
        return self._request("GET", "/v1/usage")

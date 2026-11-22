"""Shared exception base for the MindGraph Python SDK."""

from __future__ import annotations

from typing import Any


class MindGraphError(Exception):
    def __init__(self, message: str, status: int, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body
        fields = body if isinstance(body, dict) else {}
        self.code: str | None = fields.get("code") if isinstance(fields.get("code"), str) else None
        self.retriable: bool | None = (
            fields.get("retriable") if isinstance(fields.get("retriable"), bool) else None
        )

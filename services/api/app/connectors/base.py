"""Base connector types: structured errors, shared helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectorError(Exception):
    """Structured error for external provider failures.

    Every connector must raise this instead of leaking raw HTTP errors
    to the API layer. The API handler translates it into an ErrorResponse.
    """

    provider: str
    message: str
    status_code: int | None = None
    request_id: str | None = None
    retryable: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        parts = [f"[{self.provider}]"]
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.message)
        if self.request_id:
            parts.append(f"(request_id={self.request_id})")
        return " ".join(parts)


def new_request_id() -> str:
    """Generate a short request identifier for traceability."""
    return uuid.uuid4().hex[:12]

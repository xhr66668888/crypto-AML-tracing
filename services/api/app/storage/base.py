"""Abstract storage adapter interface.

All storage implementations (InMemoryStore, PostgresStore) must implement this
interface to ensure API routes and domain services remain storage-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.domain.models import (
    InvestigationCreate,
    InvestigationRecord,
    InvestigationStatus,
    ReportResponse,
    RiskLevel,
    ScreeningResponse,
    WatchlistEntry,
)


class StorageAdapter(ABC):
    """Abstract base class defining the storage contract for V1 API endpoints."""

    # ── Investigation CRUD ──────────────────────────────────────────────────

    @abstractmethod
    def create_investigation(
        self, payload: InvestigationCreate, target_type: str
    ) -> InvestigationRecord:
        """Create a new investigation record and return it."""
        ...

    @abstractmethod
    def get_investigation(self, investigation_id: str) -> InvestigationRecord:
        """Return an investigation by ID. Raises KeyError if not found."""
        ...

    @abstractmethod
    def list_investigations(self) -> list[InvestigationStatus]:
        """Return all investigations sorted by created_at descending."""
        ...

    @abstractmethod
    def complete_investigation(
        self,
        investigation_id: str,
        graph: Any,
        risk: Any,
    ) -> None:
        """Mark an investigation as completed with graph and risk data."""
        ...

    @abstractmethod
    def fail_investigation(self, investigation_id: str, message: str) -> None:
        """Mark an investigation as failed with an error message."""
        ...

    @abstractmethod
    def add_report(self, investigation_id: str, report: ReportResponse) -> None:
        """Append an AI report to an investigation."""
        ...

    # ── Screening Event CRUD ────────────────────────────────────────────────

    @abstractmethod
    def add_screening_event(self, event: ScreeningResponse) -> ScreeningResponse:
        """Store a screening event and return it."""
        ...

    @abstractmethod
    def list_screening_events(self) -> list[ScreeningResponse]:
        """Return all screening events sorted by created_at descending."""
        ...

    @abstractmethod
    def get_screening_event(self, event_id: str) -> ScreeningResponse:
        """Return a screening event by ID. Raises KeyError if not found."""
        ...

    # ── Watchlist CRUD ──────────────────────────────────────────────────────

    @abstractmethod
    def upsert_watchlist_entry(self, entry: WatchlistEntry) -> WatchlistEntry:
        """Insert or update a watchlist entry. Returns the entry."""
        ...

    @abstractmethod
    def list_watchlist_entries(self) -> list[WatchlistEntry]:
        """Return all watchlist entries sorted by address."""
        ...

    @abstractmethod
    def get_watchlist_entry(self, address: str) -> WatchlistEntry:
        """Return a watchlist entry by address. Raises KeyError if not found."""
        ...

    @abstractmethod
    def delete_watchlist_entry(self, address: str) -> bool:
        """Delete a watchlist entry. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def get_watchlist_map(self) -> dict[str, WatchlistEntry]:
        """Return address→entry mapping for risk scoring lookups."""
        ...

    @abstractmethod
    def clear_watchlist(self) -> None:
        """Remove all watchlist entries."""
        ...

    # ── Risk Source Hit CRUD ────────────────────────────────────────────────

    @abstractmethod
    def add_risk_source_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        """Store a risk source hit record."""
        ...

    @abstractmethod
    def list_risk_source_hits(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return risk source hits, optionally filtered by investigation or screening event."""
        ...

    # ── Pattern Signal CRUD ─────────────────────────────────────────────────

    @abstractmethod
    def add_pattern_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Store a pattern signal record."""
        ...

    @abstractmethod
    def list_pattern_signals(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return pattern signals, optionally filtered by investigation or screening event."""
        ...

    # ── Network Metrics CRUD ────────────────────────────────────────────────

    @abstractmethod
    def add_network_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        """Store a network metric record."""
        ...

    @abstractmethod
    def list_network_metrics(self, investigation_id: str) -> list[dict[str, Any]]:
        """Return network metrics for an investigation."""
        ...

    # ── AI Report CRUD ──────────────────────────────────────────────────────

    @abstractmethod
    def add_ai_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Store an AI report record."""
        ...

    @abstractmethod
    def list_ai_reports(self, investigation_id: str) -> list[dict[str, Any]]:
        """Return AI reports for an investigation."""
        ...

    # ── Audit Log ───────────────────────────────────────────────────────────

    @abstractmethod
    def append_audit_log(
        self,
        action: str,
        subject: str,
        actor: str = "local-user",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an audit log entry."""
        ...

    @abstractmethod
    def list_audit_logs(
        self,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return audit logs, optionally filtered by actor."""
        ...

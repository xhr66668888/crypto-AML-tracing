"""Abstract storage adapter interface.

All storage implementations (InMemoryStore) must implement this interface to
ensure API routes and domain services remain storage-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import (
    InvestigationCreate,
    InvestigationRecord,
    InvestigationStatus,
    ReportResponse,
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

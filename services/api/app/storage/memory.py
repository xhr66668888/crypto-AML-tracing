"""In-memory storage adapter (default for V1).

Implements the StorageAdapter interface for V1 API endpoints.
Data is lost on process restart — acceptable for demo/MVP usage.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models import (
    InvestigationCreate,
    InvestigationGraph,
    InvestigationRecord,
    InvestigationStatus,
    ReportResponse,
    RiskResponse,
    ScreeningResponse,
    WatchlistEntry,
)
from app.storage.base import StorageAdapter


class InMemoryStore(StorageAdapter):
    """Simple local store for MVP runs.

    The persistence boundary is deliberately isolated so a future persistence
    adapter can replace this without changing API routes or domain services.
    """

    def __init__(self) -> None:
        self._records: dict[str, InvestigationRecord] = {}
        self._watchlist: dict[str, WatchlistEntry] = {}
        self._screenings: dict[str, ScreeningResponse] = {}

    # ── Investigation CRUD ──────────────────────────────────────────────────

    def create_investigation(
        self, payload: InvestigationCreate, target_type: str
    ) -> InvestigationRecord:
        investigation_id = str(uuid4())
        status = InvestigationStatus(
            id=investigation_id,
            target=payload.target.lower(),
            target_type=target_type,
            chain_id=payload.chain_id,
            asset=payload.asset,
            token_contract_address=payload.token_contract_address,
            depth=payload.depth,
            mode=payload.mode,
            status="running",
            created_at=datetime.now(UTC),
        )
        record = InvestigationRecord(status=status)
        self._records[investigation_id] = record
        return record

    def get_investigation(self, investigation_id: str) -> InvestigationRecord:
        if investigation_id not in self._records:
            raise KeyError(investigation_id)
        return self._records[investigation_id]

    def list_investigations(self) -> list[InvestigationStatus]:
        return sorted(
            (record.status for record in self._records.values()),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def complete_investigation(
        self,
        investigation_id: str,
        graph: InvestigationGraph,
        risk: RiskResponse,
    ) -> None:
        record = self.get_investigation(investigation_id)
        record.graph = graph
        record.risk = risk
        record.status.status = "completed"
        record.status.completed_at = datetime.now(UTC)
        record.status.summary = (
            f"{len(graph.nodes)} addresses, {len(graph.edges)} transfers, "
            f"final risk {risk.final_risk_level.value} ({risk.final_risk_score:.1f})."
        )

    def fail_investigation(self, investigation_id: str, message: str) -> None:
        record = self.get_investigation(investigation_id)
        record.status.status = "failed"
        record.status.summary = message
        record.status.completed_at = datetime.now(UTC)

    def add_report(self, investigation_id: str, report: ReportResponse) -> None:
        self.get_investigation(investigation_id).reports.append(report)

    # ── Screening Event CRUD ────────────────────────────────────────────────

    def add_screening_event(self, event: ScreeningResponse) -> ScreeningResponse:
        self._screenings[event.id] = event
        return event

    def list_screening_events(self) -> list[ScreeningResponse]:
        return sorted(
            self._screenings.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

    # ── Watchlist CRUD ──────────────────────────────────────────────────────

    def upsert_watchlist_entry(self, entry: WatchlistEntry) -> WatchlistEntry:
        normalized = entry.model_copy(update={"address": entry.address.lower()})
        self._watchlist[normalized.address] = normalized
        return normalized

    def list_watchlist_entries(self) -> list[WatchlistEntry]:
        return sorted(self._watchlist.values(), key=lambda item: item.address)

    def get_watchlist_entry(self, address: str) -> WatchlistEntry:
        key = address.lower()
        if key not in self._watchlist:
            raise KeyError(address)
        return self._watchlist[key]

    def delete_watchlist_entry(self, address: str) -> bool:
        key = address.lower()
        if key in self._watchlist:
            del self._watchlist[key]
            return True
        return False

    def get_watchlist_map(self) -> dict[str, WatchlistEntry]:
        return dict(self._watchlist)

    def clear_watchlist(self) -> None:
        self._watchlist.clear()

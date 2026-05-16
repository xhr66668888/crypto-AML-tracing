"""In-memory storage adapter (default when no DATABASE_URL is configured).

Implements the full StorageAdapter interface for V1 API endpoints.
Data is lost on process restart — acceptable for demo/MVP usage.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.models import (
    InvestigationCreate,
    InvestigationGraph,
    InvestigationRecord,
    InvestigationStatus,
    ReportResponse,
    RiskResponse,
    ScreeningResponse,
    TargetType,
    WatchlistEntry,
)
from app.storage.base import StorageAdapter


class InMemoryStore(StorageAdapter):
    """Simple local store for MVP runs.

    The persistence boundary is deliberately isolated so a PostgreSQL adapter can
    replace this without changing API routes or domain services.
    """

    def __init__(self) -> None:
        self._records: dict[str, InvestigationRecord] = {}
        self._watchlist: dict[str, WatchlistEntry] = {}
        self._screenings: dict[str, ScreeningResponse] = {}
        self._risk_source_hits: list[dict[str, Any]] = []
        self._pattern_signals: list[dict[str, Any]] = []
        self._network_metrics: list[dict[str, Any]] = []
        self._ai_reports: list[dict[str, Any]] = []
        self._audit_logs: list[dict[str, Any]] = []

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

    def get_screening_event(self, event_id: str) -> ScreeningResponse:
        if event_id not in self._screenings:
            raise KeyError(event_id)
        return self._screenings[event_id]

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

    # ── Risk Source Hit CRUD ────────────────────────────────────────────────

    def add_risk_source_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        if "id" not in hit:
            hit["id"] = str(uuid4())
        if "created_at" not in hit:
            hit["created_at"] = datetime.now(UTC).isoformat()
        self._risk_source_hits.append(hit)
        return hit

    def list_risk_source_hits(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        results = self._risk_source_hits
        if investigation_id is not None:
            results = [h for h in results if h.get("investigation_id") == investigation_id]
        if screening_event_id is not None:
            results = [h for h in results if h.get("screening_event_id") == screening_event_id]
        return results

    # ── Pattern Signal CRUD ─────────────────────────────────────────────────

    def add_pattern_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        if "id" not in signal:
            signal["id"] = str(uuid4())
        if "created_at" not in signal:
            signal["created_at"] = datetime.now(UTC).isoformat()
        self._pattern_signals.append(signal)
        return signal

    def list_pattern_signals(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        results = self._pattern_signals
        if investigation_id is not None:
            results = [s for s in results if s.get("investigation_id") == investigation_id]
        if screening_event_id is not None:
            results = [s for s in results if s.get("screening_event_id") == screening_event_id]
        return results

    # ── Network Metrics CRUD ────────────────────────────────────────────────

    def add_network_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        if "id" not in metric:
            metric["id"] = str(uuid4())
        if "created_at" not in metric:
            metric["created_at"] = datetime.now(UTC).isoformat()
        self._network_metrics.append(metric)
        return metric

    def list_network_metrics(self, investigation_id: str) -> list[dict[str, Any]]:
        return [m for m in self._network_metrics if m.get("investigation_id") == investigation_id]

    # ── AI Report CRUD ──────────────────────────────────────────────────────

    def add_ai_report(self, report: dict[str, Any]) -> dict[str, Any]:
        if "id" not in report:
            report["id"] = str(uuid4())
        if "created_at" not in report:
            report["created_at"] = datetime.now(UTC).isoformat()
        self._ai_reports.append(report)
        return report

    def list_ai_reports(self, investigation_id: str) -> list[dict[str, Any]]:
        return [r for r in self._ai_reports if r.get("investigation_id") == investigation_id]

    # ── Audit Log ───────────────────────────────────────────────────────────

    def append_audit_log(
        self,
        action: str,
        subject: str,
        actor: str = "local-user",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid4()),
            "actor": actor,
            "action": action,
            "subject": subject,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._audit_logs.append(entry)
        return entry

    def list_audit_logs(
        self,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        results = self._audit_logs
        if actor is not None:
            results = [log for log in results if log.get("actor") == actor]
        return sorted(results, key=lambda x: x["created_at"], reverse=True)[:limit]

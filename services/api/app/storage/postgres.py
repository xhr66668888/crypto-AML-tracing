"""PostgreSQL storage adapter.

Requires DATABASE_URL to be set. Uses psycopg2 for synchronous operations.
This is a placeholder implementation — full SQL queries will be added when
PostgreSQL integration is activated.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.models import (
    InvestigationCreate,
    InvestigationRecord,
    InvestigationStatus,
    ReportResponse,
    ScreeningResponse,
    WatchlistEntry,
)
from app.storage.base import StorageAdapter


class PostgresStore(StorageAdapter):
    """PostgreSQL-backed storage adapter.

    This implementation maps the StorageAdapter interface to SQL queries against
    the schema defined in docs/database/schema.sql.

    Usage:
        store = PostgresStore(dsn="postgresql://user:pass@localhost:5432/aml")
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("DATABASE_URL", "")
        if not self._dsn:
            raise ValueError("DATABASE_URL must be set to use PostgresStore")
        # Lazy connection — only connect when first query runs
        self._conn = None

    def _get_conn(self):
        """Get or create a database connection."""
        if self._conn is None:
            try:
                import psycopg2
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = False
            except ImportError:
                raise ImportError(
                    "psycopg2 is required for PostgresStore. "
                    "Install with: pip install psycopg2-binary"
                )
        return self._conn

    def _execute(self, query: str, params: tuple | None = None) -> Any:
        """Execute a query and return cursor."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(query, params)
        return cur

    def _fetchone(self, query: str, params: tuple | None = None) -> dict | None:
        """Execute query and return single row as dict."""
        cur = self._execute(query, params)
        row = cur.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))

    def _fetchall(self, query: str, params: tuple | None = None) -> list[dict]:
        """Execute query and return all rows as dicts."""
        cur = self._execute(query, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]

    def _commit(self):
        """Commit current transaction."""
        conn = self._get_conn()
        conn.commit()

    # ── Investigation CRUD ──────────────────────────────────────────────────

    def create_investigation(
        self, payload: InvestigationCreate, target_type: str
    ) -> InvestigationRecord:
        investigation_id = str(uuid4())
        now = datetime.now(UTC)
        self._execute(
            """INSERT INTO investigations (id, target, target_type, chain_id, depth, mode, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (investigation_id, payload.target.lower(), target_type,
             payload.chain_id, payload.depth, payload.mode.value, "running", now),
        )
        self._commit()
        status = InvestigationStatus(
            id=investigation_id,
            target=payload.target.lower(),
            target_type=target_type,
            chain_id=payload.chain_id,
            depth=payload.depth,
            mode=payload.mode,
            status="running",
            created_at=now,
        )
        return InvestigationRecord(status=status)

    def get_investigation(self, investigation_id: str) -> InvestigationRecord:
        row = self._fetchone(
            "SELECT * FROM investigations WHERE id = %s",
            (investigation_id,),
        )
        if row is None:
            raise KeyError(investigation_id)
        status = InvestigationStatus(
            id=row["id"],
            target=row["target"],
            target_type=row["target_type"],
            chain_id=row["chain_id"],
            depth=row["depth"],
            mode=row["mode"],
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
            summary=row.get("summary"),
        )
        return InvestigationRecord(status=status)

    def list_investigations(self) -> list[InvestigationStatus]:
        rows = self._fetchall(
            "SELECT * FROM investigations ORDER BY created_at DESC"
        )
        return [
            InvestigationStatus(
                id=row["id"],
                target=row["target"],
                target_type=row["target_type"],
                chain_id=row["chain_id"],
                depth=row["depth"],
                mode=row["mode"],
                status=row["status"],
                created_at=row["created_at"],
                completed_at=row.get("completed_at"),
                summary=row.get("summary"),
            )
            for row in rows
        ]

    def complete_investigation(
        self,
        investigation_id: str,
        graph: Any,
        risk: Any,
    ) -> None:
        now = datetime.now(UTC)
        summary = (
            f"{len(graph.nodes)} addresses, {len(graph.edges)} transfers, "
            f"final risk {risk.final_risk_level.value} ({risk.final_risk_score:.1f})."
        )
        self._execute(
            """UPDATE investigations
               SET status = 'completed', completed_at = %s, summary = %s
               WHERE id = %s""",
            (now, summary, investigation_id),
        )
        self._commit()

    def fail_investigation(self, investigation_id: str, message: str) -> None:
        now = datetime.now(UTC)
        self._execute(
            """UPDATE investigations
               SET status = 'failed', completed_at = %s, summary = %s
               WHERE id = %s""",
            (now, message, investigation_id),
        )
        self._commit()

    def add_report(self, investigation_id: str, report: ReportResponse) -> None:
        # Store in ai_reports table
        self._execute(
            """INSERT INTO ai_reports (id, investigation_id, model, report_markdown, used_external_llm, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(uuid4()), investigation_id, report.model,
             report.report_markdown, report.used_external_llm, report.generated_at),
        )
        self._commit()

    # ── Screening Event CRUD ────────────────────────────────────────────────

    def add_screening_event(self, event: ScreeningResponse) -> ScreeningResponse:
        self._execute(
            """INSERT INTO screening_events
               (id, chain_id, asset, direction, from_address, to_address, amount,
                risk_score, risk_level, disposition, evidence_summary,
                recommended_actions, data_freshness, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (event.id, event.chain_id, event.asset.value, event.direction.value,
             event.from_address, event.to_address, event.amount,
             event.risk_score, event.risk_level.value, event.disposition.value,
             str(event.evidence_summary), str(event.recommended_actions),
             str(event.data_freshness), event.created_at),
        )
        self._commit()
        return event

    def list_screening_events(self) -> list[ScreeningResponse]:
        rows = self._fetchall(
            "SELECT * FROM screening_events ORDER BY created_at DESC"
        )
        # TODO: Reconstruct ScreeningResponse from rows
        return []

    def get_screening_event(self, event_id: str) -> ScreeningResponse:
        row = self._fetchone(
            "SELECT * FROM screening_events WHERE id = %s",
            (event_id,),
        )
        if row is None:
            raise KeyError(event_id)
        # TODO: Reconstruct ScreeningResponse from row
        raise NotImplementedError("PostgresStore.get_screening_event not fully implemented")

    # ── Watchlist CRUD ──────────────────────────────────────────────────────

    def upsert_watchlist_entry(self, entry: WatchlistEntry) -> WatchlistEntry:
        normalized = entry.model_copy(update={"address": entry.address.lower()})
        self._execute(
            """INSERT INTO watchlist_entries (address, label, category, severity, notes, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (address) DO UPDATE
               SET label = EXCLUDED.label, category = EXCLUDED.category,
                   severity = EXCLUDED.severity, notes = EXCLUDED.notes,
                   updated_at = EXCLUDED.updated_at""",
            (normalized.address, normalized.label, normalized.category,
             normalized.severity.value, normalized.notes, datetime.now(UTC)),
        )
        self._commit()
        return normalized

    def list_watchlist_entries(self) -> list[WatchlistEntry]:
        rows = self._fetchall(
            "SELECT * FROM watchlist_entries ORDER BY address"
        )
        return [
            WatchlistEntry(
                address=row["address"],
                label=row["label"],
                category=row["category"],
                severity=row["severity"],
                notes=row.get("notes", ""),
            )
            for row in rows
        ]

    def get_watchlist_entry(self, address: str) -> WatchlistEntry:
        row = self._fetchone(
            "SELECT * FROM watchlist_entries WHERE address = %s",
            (address.lower(),),
        )
        if row is None:
            raise KeyError(address)
        return WatchlistEntry(
            address=row["address"],
            label=row["label"],
            category=row["category"],
            severity=row["severity"],
            notes=row.get("notes", ""),
        )

    def delete_watchlist_entry(self, address: str) -> bool:
        cur = self._execute(
            "DELETE FROM watchlist_entries WHERE address = %s",
            (address.lower(),),
        )
        self._commit()
        return cur.rowcount > 0

    def get_watchlist_map(self) -> dict[str, WatchlistEntry]:
        entries = self.list_watchlist_entries()
        return {entry.address: entry for entry in entries}

    def clear_watchlist(self) -> None:
        self._execute("DELETE FROM watchlist_entries")
        self._commit()

    # ── Risk Source Hit CRUD ────────────────────────────────────────────────

    def add_risk_source_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        hit_id = hit.get("id", str(uuid4()))
        self._execute(
            """INSERT INTO risk_source_hits
               (id, investigation_id, screening_event_id, address, source,
                category, severity, label, evidence, confidence, direct_hit,
                source_updated_at, raw_payload, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (hit_id, hit.get("investigation_id"), hit.get("screening_event_id"),
             hit["address"], hit["source"], hit["category"], hit["severity"],
             hit["label"], hit["evidence"], hit.get("confidence", 1),
             hit.get("direct_hit", False), hit.get("source_updated_at"),
             str(hit.get("raw_payload", {})),
             hit.get("created_at", datetime.now(UTC))),
        )
        self._commit()
        hit["id"] = hit_id
        return hit

    def list_risk_source_hits(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM risk_source_hits WHERE 1=1"
        params: list[Any] = []
        if investigation_id:
            query += " AND investigation_id = %s"
            params.append(investigation_id)
        if screening_event_id:
            query += " AND screening_event_id = %s"
            params.append(screening_event_id)
        return self._fetchall(query, tuple(params))

    # ── Pattern Signal CRUD ─────────────────────────────────────────────────

    def add_pattern_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        signal_id = signal.get("id", str(uuid4()))
        self._execute(
            """INSERT INTO pattern_signals
               (id, investigation_id, screening_event_id, name, severity,
                score, subject, evidence, confidence, metadata, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (signal_id, signal.get("investigation_id"), signal.get("screening_event_id"),
             signal["name"], signal["severity"], signal["score"],
             signal["subject"], signal["evidence"],
             signal.get("confidence", 0.75), str(signal.get("metadata", {})),
             signal.get("created_at", datetime.now(UTC))),
        )
        self._commit()
        signal["id"] = signal_id
        return signal

    def list_pattern_signals(
        self,
        investigation_id: str | None = None,
        screening_event_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM pattern_signals WHERE 1=1"
        params: list[Any] = []
        if investigation_id:
            query += " AND investigation_id = %s"
            params.append(investigation_id)
        if screening_event_id:
            query += " AND screening_event_id = %s"
            params.append(screening_event_id)
        return self._fetchall(query, tuple(params))

    # ── Network Metrics CRUD ────────────────────────────────────────────────

    def add_network_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        metric_id = metric.get("id", str(uuid4()))
        self._execute(
            """INSERT INTO network_metrics
               (id, investigation_id, name, value, subject, metadata, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (metric_id, metric["investigation_id"], metric["name"],
             metric["value"], metric.get("subject"),
             str(metric.get("metadata", {})),
             metric.get("created_at", datetime.now(UTC))),
        )
        self._commit()
        metric["id"] = metric_id
        return metric

    def list_network_metrics(self, investigation_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM network_metrics WHERE investigation_id = %s",
            (investigation_id,),
        )

    # ── AI Report CRUD ──────────────────────────────────────────────────────

    def add_ai_report(self, report: dict[str, Any]) -> dict[str, Any]:
        report_id = report.get("id", str(uuid4()))
        self._execute(
            """INSERT INTO ai_reports
               (id, investigation_id, model, report_markdown, used_external_llm, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (report_id, report["investigation_id"], report["model"],
             report["report_markdown"], report.get("used_external_llm", False),
             report.get("created_at", datetime.now(UTC))),
        )
        self._commit()
        report["id"] = report_id
        return report

    def list_ai_reports(self, investigation_id: str) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM ai_reports WHERE investigation_id = %s",
            (investigation_id,),
        )

    # ── Audit Log ───────────────────────────────────────────────────────────

    def append_audit_log(
        self,
        action: str,
        subject: str,
        actor: str = "local-user",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry_id = str(uuid4())
        now = datetime.now(UTC)
        self._execute(
            """INSERT INTO audit_logs (id, actor, action, subject, metadata, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (entry_id, actor, action, subject, str(metadata or {}), now),
        )
        self._commit()
        return {
            "id": entry_id,
            "actor": actor,
            "action": action,
            "subject": subject,
            "metadata": metadata or {},
            "created_at": now.isoformat(),
        }

    def list_audit_logs(
        self,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if actor:
            return self._fetchall(
                "SELECT * FROM audit_logs WHERE actor = %s ORDER BY created_at DESC LIMIT %s",
                (actor, limit),
            )
        return self._fetchall(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )

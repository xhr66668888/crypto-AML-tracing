from __future__ import annotations

import csv
import io
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.connectors.etherscan import EtherscanClient
from app.connectors.goplus import GoPlusClient
from app.core.config import get_settings
from app.domain.graph_builder import GraphBuilder
from app.domain.models import (
    DIRECT_HIT_CATEGORIES,
    InvestigationCreate,
    ReportRequest,
    ScreeningTransactionCreate,
    WatchlistEntry,
    WatchlistImportRequest,
    WatchlistImportResult,
    WatchlistImportError,
)
from app.domain.patterns import PatternAnalyzer
from app.domain.risk_intel import RiskIntelAggregator
from app.domain.scoring import RiskScoringEngine
from app.ml.raindrop_scorer import RaindropAmlScorer
from app.services.investigation import InvestigationService
from app.services.reporting import DeepSeekReporter
from app.services.screening import ScreeningService
from app.storage import get_store

settings = get_settings()
store = get_store()
etherscan = EtherscanClient(
    api_key=settings.etherscan_api_key,
    base_url=settings.etherscan_base_url,
    chain_id=settings.chain_id,
    demo_mode=settings.demo_mode,
    timeout_seconds=settings.etherscan_timeout_seconds,
    max_retries=settings.connector_max_retries,
)
goplus = GoPlusClient(
    token=settings.goplus_token,
    demo_mode=settings.demo_mode,
    timeout_seconds=settings.goplus_timeout_seconds,
    max_retries=settings.connector_max_retries,
)
intel = RiskIntelAggregator(goplus)
raindrop = RaindropAmlScorer()
patterns = PatternAnalyzer()
graph_builder = GraphBuilder(etherscan, settings.max_stable_nodes, settings.max_experimental_nodes)
scoring = RiskScoringEngine(intel, raindrop, patterns)
investigations = InvestigationService(store, graph_builder, scoring)
screening = ScreeningService(store, graph_builder, scoring, patterns)
reporter = DeepSeekReporter(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "demo_mode": settings.demo_mode}


@app.post("/api/v1/investigations")
async def create_investigation(payload: InvestigationCreate):
    return await investigations.create_and_run(payload)


@app.post("/api/v1/screening/transactions")
async def screen_transaction(payload: ScreeningTransactionCreate):
    try:
        return await screening.screen_transaction(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/screening/events")
async def list_screening_events():
    return store.list_screening_events()


@app.get("/api/v1/investigations")
async def list_investigations():
    return store.list_investigations()


@app.get("/api/v1/investigations/{investigation_id}")
async def get_investigation(investigation_id: str):
    return _get_record(investigation_id).status


@app.get("/api/v1/investigations/{investigation_id}/graph")
async def get_graph(investigation_id: str):
    record = _get_record(investigation_id)
    if not record.graph:
        raise HTTPException(status_code=409, detail="Investigation graph is not ready.")
    return record.graph


@app.get("/api/v1/investigations/{investigation_id}/risk")
async def get_risk(investigation_id: str):
    record = _get_record(investigation_id)
    if not record.risk:
        raise HTTPException(status_code=409, detail="Investigation risk is not ready.")
    return record.risk


@app.post("/api/v1/investigations/{investigation_id}/reports")
async def create_report(investigation_id: str, payload: ReportRequest):
    record = _get_record(investigation_id)
    report = await reporter.generate(record, language=payload.language, include_raw_context=payload.include_raw_context)
    store.add_report(investigation_id, report)
    return report


@app.get("/api/v1/watchlists")
async def list_watchlist_entries():
    return store.list_watchlist_entries()


@app.post("/api/v1/watchlists")
async def upsert_watchlist_entry(payload: WatchlistEntry):
    return store.upsert_watchlist_entry(payload)


@app.post("/api/v1/watchlists/import")
async def import_watchlist(payload: WatchlistImportRequest):
    errors: list[WatchlistImportError] = []
    imported = 0
    updated = 0
    skipped = 0
    direct_hit_count = 0

    if payload.replace:
        store.clear_watchlist()

    if payload.format == "csv":
        reader = csv.DictReader(io.StringIO(payload.payload))
        for row_idx, row in enumerate(reader, start=1):
            try:
                address = row.get("address", "").strip()
                if not address:
                    raise ValueError("missing address")
                entry = WatchlistEntry(
                    address=address,
                    label=row.get("label", "").strip() or "unlabeled",
                    category=row.get("category", "").strip() or payload.default_category,
                    severity=row.get("severity", "").strip() or payload.default_severity,
                    notes=row.get("notes", "").strip(),
                )
                try:
                    store.get_watchlist_entry(entry.address.lower())
                    is_update = True
                except KeyError:
                    is_update = False
                store.upsert_watchlist_entry(entry)
                if is_update:
                    updated += 1
                else:
                    imported += 1
                if entry.category.lower() in DIRECT_HIT_CATEGORIES:
                    direct_hit_count += 1
            except Exception as exc:
                errors.append(WatchlistImportError(row=row_idx, reason=str(exc)))
    elif payload.format == "json":
        try:
            rows = json.loads(payload.payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
        for row_idx, row in enumerate(rows, start=1):
            try:
                address = row.get("address", "").strip()
                if not address:
                    raise ValueError("missing address")
                entry = WatchlistEntry(
                    address=address,
                    label=row.get("label", "").strip() or "unlabeled",
                    category=row.get("category", "").strip() or payload.default_category,
                    severity=row.get("severity", payload.default_severity),
                    notes=row.get("notes", "").strip(),
                )
                try:
                    store.get_watchlist_entry(entry.address.lower())
                    is_update = True
                except KeyError:
                    is_update = False
                store.upsert_watchlist_entry(entry)
                if is_update:
                    updated += 1
                else:
                    imported += 1
                if entry.category.lower() in DIRECT_HIT_CATEGORIES:
                    direct_hit_count += 1
            except Exception as exc:
                errors.append(WatchlistImportError(row=row_idx, reason=str(exc)))

    return WatchlistImportResult(
        imported=imported,
        updated=updated,
        skipped=skipped,
        direct_hit_count=direct_hit_count,
        errors=errors,
    )


@app.get("/api/v1/investigations/{investigation_id}/reports")
async def list_reports(investigation_id: str):
    record = _get_record(investigation_id)
    return record.reports


def _get_record(investigation_id: str):
    try:
        return store.get_investigation(investigation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found.") from exc

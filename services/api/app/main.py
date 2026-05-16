from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.connectors.etherscan import EtherscanClient
from app.connectors.goplus import GoPlusClient
from app.core.config import get_settings
from app.domain.graph_builder import GraphBuilder
from app.domain.models import InvestigationCreate, ReportRequest, ScreeningTransactionCreate, WatchlistEntry
from app.domain.patterns import PatternAnalyzer
from app.domain.risk_intel import RiskIntelAggregator
from app.domain.scoring import RiskScoringEngine
from app.ml.raindrop_aml import RaindropAmlScorer
from app.services.investigation import InvestigationService
from app.services.reporting import DeepSeekReporter
from app.services.screening import ScreeningService
from app.storage.memory import InMemoryStore

settings = get_settings()
store = InMemoryStore()
etherscan = EtherscanClient(
    api_key=settings.etherscan_api_key,
    base_url=settings.etherscan_base_url,
    chain_id=settings.chain_id,
    demo_mode=settings.demo_mode,
)
goplus = GoPlusClient(token=settings.goplus_token, demo_mode=settings.demo_mode)
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


def _get_record(investigation_id: str):
    try:
        return store.get_investigation(investigation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found.") from exc

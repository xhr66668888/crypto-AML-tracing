# V1 API Contract Changelog

**Frozen**: 2026-05-16
**Owner**: `aml-architect`
**Status**: FROZEN — changes require `aml-architect` approval.

---

## Task 4 Amendment — 2026-05-24

`ScreeningTransactionCreate.asset` is now an uppercase symbol string rather than
an `ETH | USDT | USDC` enum. The backend accepts built-in Ethereum mainnet
assets `ETH`, `USDT`, `USDC`, `DAI`, `WETH`, and `WBTC`, and supports custom
ERC-20 assets when the request includes `asset_type="erc20"` and
`token_address`.

ERC-20 screening now uses Etherscan `tokentx` graph context when a token
contract is known, preserves token metadata on graph edges, checks GoPlus token
contract risk, and still performs Circle/Tether issuer blacklist checks for
USDC/USDT by symbol or token address.

---

## Task 5 Amendment — 2026-05-24

Pre-transaction screening now builds a lightweight two-sided context graph.
The backend expands both `from_address` and `to_address` to at most 2 hops and
6 recent transactions per address. For ERC-20 screening, the same limits apply
to token-transfer graph context.

The screening response can now include context-derived pattern signals:

- `one_hop_risky_exposure`
- `two_hop_risky_exposure`
- `short_time_repeated_transfers`

These are evidence signals only; they support pre-transaction decisions but do
not claim complete fund provenance.

Context source-hit handling was tightened after implementation review:

- `source_hits` in `ScreeningResponse` now represent transaction-party hits or
  provider checks directly attached to the screened asset/address.
- OFAC/sanctions/stablecoin hits found only in bounded 1-hop or 2-hop context
  are converted into exposure `pattern_signals`.
- Direct hits on `from_address` or `to_address` still force
  `hold_for_manual_review`; context-only exposure normally drives `review`.

---

## Task 6 Amendment — 2026-05-24

Decision policy is now separated from numeric score generation in
`RiskDecisionPolicy`.

- `score` remains the numeric risk intensity.
- `disposition` is derived by policy thresholds and direct-hit rules.
- Direct-hit categories still force `hold_for_manual_review` even when the
  numeric score is low.
- Provider-degraded signals such as `provider_unavailable`,
  `stablecoin_blacklist_unavailable`, and `token_contract_risk_unavailable`
  produce `review` and a retry-oriented recommended action instead of being
  treated as clean.

The legacy helpers `decide_disposition()` and `recommended_actions()` remain
available and delegate to the default policy, so API contracts and service
callers are unchanged.

---

## Transaction Hash Screening Amendment — 2026-05-24

`POST /api/v1/screening/transactions` now accepts tx-hash-only screening
requests. When `tx_hash` is provided without manual transfer fields, the backend
uses Etherscan to resolve:

- `from_address`
- `to_address`
- `amount`
- `asset`
- `asset_type`
- `token_address`

Native ETH transfers are decoded from the transaction value. ERC-20 transfers
are decoded from receipt `Transfer` logs; token symbol/name/decimals are read
through Etherscan proxy `eth_call` where available.

---

## Hard Invariants

1. Every risk conclusion must point to a `source_hit`, `pattern_signal`, or `evidence` row. No invented facts.
2. Direct-hit categories (`ofac`, `pep`, `sanctions`, `sanctioned`, `circle_blacklist`, `tether_blacklist`, `stablecoin_blacklist`) FORCE `hold_for_manual_review` regardless of behavioural score.
3. `raindrop_score` is advisory; never overrides source-backed evidence.
4. `RaindropAmlScorer.predict(graph)` signature is frozen: `(InvestigationGraph) -> RaindropResult`.
5. Demo data must be labelled `demo` in API responses and reports.

---

## Endpoints

### GET /health

Health check endpoint.

**Response** `200 OK`:
```json
{
  "status": "ok",
  "demo_mode": true
}
```

---

### POST /api/v1/screening/transactions

Pre-withdrawal transfer screening. Returns risk score, disposition, findings, pattern signals, and source hits.

**Request** (`ScreeningTransactionCreate`):
```json
{
  "chain_id": "1",
  "asset": "USDC",
  "asset_type": "erc20",
  "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
  "direction": "outbound",
  "from_address": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
  "to_address": "0x1111111111111111111111111111111111111111",
  "amount": 9500,
  "customer_id": "cust-001",
  "team_id": "team-risk",
  "tx_hash": null,
  "timestamp": null
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `chain_id` | string | No | `"1"` | Ethereum chain ID |
| `asset` | string | No | `"ETH"` | Built-ins: `ETH`, `USDT`, `USDC`, `DAI`, `WETH`, `WBTC`; custom ERC-20 requires `token_address` |
| `asset_type` | string | No | `null` | Optional: `native` or `erc20` |
| `token_address` | string | No | `null` | Required for custom ERC-20 assets; optional for built-in Ethereum mainnet tokens |
| `direction` | enum | No | `"outbound"` | One of: `inbound`, `outbound` |
| `from_address` | string | Conditional | — | Required unless `tx_hash` is provided |
| `to_address` | string | Conditional | — | Required unless `tx_hash` is provided |
| `amount` | float | Conditional | — | Required unless `tx_hash` is provided |
| `customer_id` | string | No | `null` | Operator-assigned customer ID |
| `team_id` | string | No | `null` | Operator-assigned team ID |
| `tx_hash` | string | No | `null` | 66-char hex transaction hash |
| `timestamp` | int | No | `null` | Unix timestamp; defaults to current time |

Tx-hash-only request:

```json
{
  "chain_id": "1",
  "tx_hash": "0x..."
}
```

**Response** `200 OK` (`ScreeningResponse`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "chain_id": "1",
  "asset": "USDC",
  "direction": "outbound",
  "from_address": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
  "to_address": "0x1111111111111111111111111111111111111111",
  "amount": 9500.0,
  "risk_score": 72.5,
  "risk_level": "high",
  "disposition": "hold_for_manual_review",
  "findings": [
    {
      "category": "ofac",
      "severity": "critical",
      "score": 95.0,
      "subject": "0x1111111111111111111111111111111111111111",
      "evidence": "OFAC SDN sanctions list hit.",
      "source": "ofac",
      "hop": 0,
      "metadata": {}
    }
  ],
  "pattern_signals": [
    {
      "name": "threshold_structuring",
      "severity": "medium",
      "score": 42.0,
      "subject": "0x1111111111111111111111111111111111111111",
      "evidence": "USDC amount 9500 is just below the 10000 review threshold.",
      "confidence": 0.78,
      "metadata": {"amount": 9500, "threshold": 10000, "asset": "USDC"}
    }
  ],
  "source_hits": [
    {
      "source": "ofac",
      "category": "ofac",
      "severity": "critical",
      "address": "0x1111111111111111111111111111111111111111",
      "label": "OFAC SDN demo",
      "evidence": "Authoritative sanctions list demo hit.",
      "confidence": 1.0,
      "source_updated_at": "2026-05-16T12:00:00Z",
      "direct_hit": true,
      "raw_payload": {}
    }
  ],
  "evidence_summary": [
    "Authoritative sanctions list demo hit.",
    "USDC amount 9500 is just below the 10000 review threshold."
  ],
  "recommended_actions": [
    "Hold funds for manual compliance review and verify the authoritative source evidence.",
    "Escalate to the sanctions/PEP review workflow before customer release."
  ],
  "data_freshness": {
    "transaction_context": "current_request",
    "graph_context": "provider_recent_transactions",
    "ofac": "2026-05-16T12:00:00Z"
  },
  "graph_investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-16T12:00:00Z"
}
```

**Error** `400 Bad Request`:
```json
{
  "detail": "Invalid Ethereum address."
}
```

---

### POST /api/v1/investigations

Create and run an investigation on an address or transaction hash.

**Request** (`InvestigationCreate`):
```json
{
  "target": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
  "chain_id": "1",
  "depth": 3,
  "mode": "stable"
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `target` | string | Yes | — | 42-char address or 66-char tx hash |
| `chain_id` | string | No | `"1"` | Ethereum chain ID |
| `depth` | int | No | `3` | 1–5 hops |
| `mode` | enum | No | `"stable"` | `stable` (3 hops, 75 nodes) or `experimental` (5 hops, 160 nodes) |

**Response** `200 OK` (`InvestigationRecord`):
```json
{
  "status": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "target": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
    "target_type": "address",
    "chain_id": "1",
    "depth": 3,
    "mode": "stable",
    "status": "completed",
    "created_at": "2026-05-16T12:00:00Z",
    "completed_at": "2026-05-16T12:00:05Z",
    "summary": "12 addresses, 18 transfers, final risk medium (45.2)."
  },
  "graph": { "..." },
  "risk": { "..." },
  "reports": []
}
```

**Error** `422 Unprocessable Entity`: Validation error (invalid target format, depth out of range).

---

### GET /api/v1/investigations

List all investigations.

**Response** `200 OK`:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "target": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
    "target_type": "address",
    "chain_id": "1",
    "depth": 3,
    "mode": "stable",
    "status": "completed",
    "created_at": "2026-05-16T12:00:00Z",
    "completed_at": "2026-05-16T12:00:05Z",
    "summary": "12 addresses, 18 transfers, final risk medium (45.2)."
  }
]
```

---

### GET /api/v1/investigations/{id}

Get a single investigation status.

**Response** `200 OK` (`InvestigationStatus`):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "target": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
  "target_type": "address",
  "chain_id": "1",
  "depth": 3,
  "mode": "stable",
  "status": "completed",
  "created_at": "2026-05-16T12:00:00Z",
  "completed_at": "2026-05-16T12:00:05Z",
  "summary": "12 addresses, 18 transfers, final risk medium (45.2)."
}
```

**Error** `404 Not Found`:
```json
{
  "detail": "Investigation not found."
}
```

---

### GET /api/v1/investigations/{id}/graph

Get the transaction graph for a completed investigation.

**Response** `200 OK` (`InvestigationGraph`):
```json
{
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "nodes": [
    {
      "id": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
      "address": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
      "label": "0x8a58...87f5",
      "hop": 0,
      "node_type": "address",
      "risk_score": 35.0,
      "risk_level": "medium",
      "tags": ["doubt_list"],
      "source": "target",
      "metadata": {}
    }
  ],
  "edges": [
    {
      "id": "0xabc...:0x8a58...:0x1111...",
      "source": "0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
      "target": "0x1111111111111111111111111111111111111111",
      "tx_hash": "0xabc123...",
      "timestamp": 1700000000,
      "value_eth": 4.2,
      "hop": 1,
      "direction": "out",
      "metadata": {}
    }
  ],
  "generated_at": "2026-05-16T12:00:05Z"
}
```

**Error** `404 Not Found`: Investigation not found.
**Error** `409 Conflict`:
```json
{
  "detail": "Investigation graph is not ready."
}
```

---

### GET /api/v1/investigations/{id}/risk

Get the risk assessment for a completed investigation.

**Response** `200 OK` (`RiskResponse`):
```json
{
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "rule_score": 72.5,
  "raindrop_score": 45.3,
  "final_risk_score": 72.5,
  "final_risk_level": "high",
  "findings": [
    {
      "category": "ofac",
      "severity": "critical",
      "score": 95.0,
      "subject": "0x1111111111111111111111111111111111111111",
      "evidence": "OFAC SDN sanctions list hit.",
      "source": "ofac",
      "hop": 0,
      "metadata": {}
    }
  ],
  "top_risk_paths": [
    ["0x8a5847fd0e592b058c026c5fdc322aee834b87f5", "0x1111111111111111111111111111111111111111"]
  ],
  "feature_summary": {
    "node_count": 12,
    "edge_count": 18,
    "max_hop": 3,
    "edge_exposure_score": 5.2,
    "pattern_signal_count": 2,
    "max_pattern_score": 68.0,
    "raindrop_adapter": "deterministic-mvp",
    "temporal_irregularity": 0.45,
    "value_dispersion": 12.3,
    "tagged_exposure_nodes": 2,
    "max_hop": 3
  },
  "pattern_signals": [
    {
      "name": "aggregation",
      "severity": "high",
      "score": 72.0,
      "subject": "0x1111111111111111111111111111111111111111",
      "evidence": "5 source addresses aggregate 12.5 ETH into one address.",
      "confidence": 0.76,
      "metadata": {"source_count": 5, "total_value_eth": 12.5}
    }
  ],
  "source_hits": [
    {
      "source": "ofac",
      "category": "ofac",
      "severity": "critical",
      "address": "0x1111111111111111111111111111111111111111",
      "label": "OFAC SDN demo",
      "evidence": "Authoritative sanctions list demo hit.",
      "confidence": 1.0,
      "source_updated_at": "2026-05-16T12:00:00Z",
      "direct_hit": true,
      "raw_payload": {}
    }
  ],
  "network_metrics": [
    {"name": "node_count", "value": 12.0, "subject": null, "metadata": {}},
    {"name": "edge_count", "value": 18.0, "subject": null, "metadata": {}},
    {"name": "graph_density", "value": 0.1364, "subject": null, "metadata": {}},
    {"name": "max_degree", "value": 8.0, "subject": "0x8a58...", "metadata": {}},
    {"name": "max_betweenness_centrality", "value": 0.4521, "subject": "0x8a58...", "metadata": {}}
  ],
  "disposition_hint": "hold_for_manual_review",
  "recommended_actions": [
    "Hold funds for manual compliance review and verify the authoritative source evidence.",
    "Escalate to the sanctions/PEP review workflow before customer release."
  ]
}
```

**Error** `404 Not Found`: Investigation not found.
**Error** `409 Conflict`:
```json
{
  "detail": "Investigation risk is not ready."
}
```

---

### POST /api/v1/investigations/{id}/reports

Generate an investigation report.

**Request** (`ReportRequest`):
```json
{
  "language": "en",
  "include_raw_context": true
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `language` | string | No | `"en"` | Report language (V1: English only) |
| `include_raw_context` | bool | No | `true` | Include raw graph in DeepSeek context |

**Response** `200 OK` (`ReportResponse`):
```json
{
  "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "local-template",
  "report_markdown": "# Investigation Report\n\n...",
  "generated_at": "2026-05-16T12:00:10Z",
  "used_external_llm": false
}
```

**Error** `404 Not Found`: Investigation not found.

---

### GET /api/v1/investigations/{id}/reports

List all reports for an investigation.

**Response** `200 OK`:
```json
[
  {
    "investigation_id": "550e8400-e29b-41d4-a716-446655440000",
    "model": "local-template",
    "report_markdown": "# Investigation Report\n\n...",
    "generated_at": "2026-05-16T12:00:10Z",
    "used_external_llm": false
  }
]
```

**Error** `404 Not Found`: Investigation not found.

---

### GET /api/v1/watchlists

List all watchlist entries.

**Response** `200 OK`:
```json
[
  {
    "address": "0x1111111111111111111111111111111111111111",
    "label": "OFAC SDN demo",
    "source": "ofac_sdn",
    "source_version": "2026-05-23",
    "category": "ofac",
    "severity": "critical",
    "evidence": "OFAC SDN address match.",
    "notes": "Authoritative sanctions list demo hit."
  }
]
```

---

### POST /api/v1/watchlists

Upsert a single watchlist entry.

**Request** (`WatchlistEntry`):
```json
{
  "address": "0x1111111111111111111111111111111111111111",
  "label": "OFAC SDN demo",
  "source": "ofac_sdn",
  "source_version": "2026-05-23",
  "category": "ofac",
  "severity": "critical",
  "evidence": "OFAC SDN address match.",
  "notes": "Authoritative sanctions list demo hit."
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `address` | string | Yes | — | 42-char hex Ethereum address |
| `label` | string | Yes | — | Human-readable label |
| `source` | string | No | `"manual_import"` | Dataset or provider source |
| `source_version` | string | No | `""` | Publication date, snapshot, or block/query timestamp |
| `category` | string | No | `"manual"` | Risk category |
| `severity` | enum | No | `"high"` | One of: `low`, `medium`, `high`, `critical` |
| `evidence` | string | No | `""` | Source-backed evidence used in risk decisions |
| `notes` | string | No | `""` | Free-text notes |

**Response** `200 OK`: Returns the upserted `WatchlistEntry`.

---

### POST /api/v1/watchlists/import

Bulk import watchlist entries from CSV or JSON.

**Request** (`WatchlistImportRequest`):
```json
{
  "format": "csv",
  "payload": "address,label,source,source_version,category,severity,evidence,notes\n0x1111111111111111111111111111111111111111,OFAC SDN,ofac_sdn,2026-05-23,ofac,critical,OFAC SDN address match.,Test",
  "default_category": "manual",
  "default_severity": "high",
  "default_source": "manual_import",
  "default_source_version": "",
  "replace": false
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `format` | enum | No | `"csv"` | `csv` or `json` |
| `payload` | string | Yes | — | CSV string or JSON array string |
| `default_category` | string | No | `"manual"` | Fallback category for rows missing it |
| `default_severity` | enum | No | `"high"` | Fallback severity for rows missing it |
| `default_source` | string | No | `"manual_import"` | Fallback source for rows missing it |
| `default_source_version` | string | No | `""` | Fallback source version for rows missing it |
| `replace` | bool | No | `false` | If `true`, clears watchlist before import |

**CSV format**: `address,label,source,source_version,category,severity,evidence,notes` (header required).
Legacy CSV files with `address,label,category,severity,notes` still import; `notes` is used as evidence when `evidence` is blank.
**JSON format**: Array of objects with keys `address`, `label`, `source`, `source_version`, `category`, `severity`, `evidence`, `notes`.

**Response** `200 OK` (`WatchlistImportResult`):
```json
{
  "imported": 5,
  "updated": 1,
  "skipped": 0,
  "direct_hit_count": 2,
  "errors": [
    {"row": 3, "reason": "Invalid Ethereum address."}
  ]
}
```

**Error** `400 Bad Request` (JSON format only):
```json
{
  "detail": "Invalid JSON: ..."
}
```

---

### GET /api/v1/screening/events

List all screening events (history).

**Response** `200 OK`: Array of `ScreeningResponse` objects (same shape as POST screening response).

---

## Frozen Interfaces

### RaindropAmlScorer.predict(graph)

```python
def predict(self, graph: InvestigationGraph) -> RaindropResult
```

- **Input**: `InvestigationGraph` (nodes + edges)
- **Output**: `RaindropResult` with fields:
  - `score: float` — risk score in [0, 100], advisory only
  - `features: dict` — feature vector, JSON-serialisable
  - `explanation: str` — human-readable score drivers
  - `model_version: str` — e.g. `"raindrop-v1-deterministic"`
- **Frozen until**: `aml-architect` approves a change.

### DIRECT_HIT_CATEGORIES

```python
DIRECT_HIT_CATEGORIES: frozenset[str] = frozenset({
    "ofac", "sanctions", "sanctioned", "pep",
    "circle_blacklist", "tether_blacklist", "stablecoin_blacklist"
})
```

Any address with a watchlist category in this set produces `direct_hit=True` on its `RiskSourceHit` and forces `disposition=hold_for_manual_review` regardless of the numeric risk score.

---

## Changes Made During Freeze

1. **Canonical Raindrop interface**: `RaindropAmlScorer.predict(graph) -> RaindropResult` is the only public surface. The duplicate `raindrop_aml.py` (returning `tuple[float, dict]`) was deleted during round-one Karpathy §2 cleanup. `scoring.py` no longer has an `isinstance(result, tuple)` branch.
2. **No endpoint path changes**: All paths match the implementation in `main.py`. Note: watchlist endpoints use `/api/v1/watchlists` (plural).
3. **No model changes**: All Pydantic models in `domain/models.py` are complete and correct.
4. **R2: dropped `language` from `ReportRequest`**: no caller existed; field silently accepted by FastAPI returned 200 with no effect; removed to match Karpathy §2 single-use rule.

---

## Endpoint Path Summary

| Method | Path | Handler |
|--------|------|---------|
| GET | `/health` | `health()` |
| POST | `/api/v1/screening/transactions` | `screen_transaction()` |
| GET | `/api/v1/screening/events` | `list_screening_events()` |
| POST | `/api/v1/investigations` | `create_investigation()` |
| GET | `/api/v1/investigations` | `list_investigations()` |
| GET | `/api/v1/investigations/{id}` | `get_investigation()` |
| GET | `/api/v1/investigations/{id}/graph` | `get_graph()` |
| GET | `/api/v1/investigations/{id}/risk` | `get_risk()` |
| POST | `/api/v1/investigations/{id}/reports` | `create_report()` |
| GET | `/api/v1/investigations/{id}/reports` | `list_reports()` |
| GET | `/api/v1/watchlists` | `list_watchlist_entries()` |
| POST | `/api/v1/watchlists` | `upsert_watchlist_entry()` |
| POST | `/api/v1/watchlists/import` | `import_watchlist()` |

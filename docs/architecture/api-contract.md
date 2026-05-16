# V1 API Contract (frozen by `aml-architect`)

Status: **Frozen for Day 1 / Day 2 implementation.** Changes require an
`aml-architect` amendment plus a `risk-logic-reviewer` verdict.

All endpoints are versioned under `/api/v1`. The API is local-first, CORS-gated,
and intended for a single Cregis risk operator host.

## 1. Conventions

### 1.1 Identifiers and assets

- `chain_id` is a numeric string. Day-1 only `"1"` (Ethereum mainnet) is supported.
- `asset` is one of `"ETH"`, `"USDT"`, `"USDC"`.
- `direction` is one of `"inbound"`, `"outbound"`.
- `address` is a 0x-prefixed 42-character hex string (case-insensitive on input;
  normalized lowercase on output).
- `tx_hash` is a 0x-prefixed 66-character hex string.

### 1.2 Risk vocabulary

- `risk_level ∈ {low, medium, high, critical}`.
- `disposition ∈ {allow, review, hold_for_manual_review, reject}`.
- Direct-hit categories that **force `hold_for_manual_review` regardless of
  behavioural score**:
  `ofac, sanctions, pep, circle_blacklist, tether_blacklist, stablecoin_blacklist`.
- Direct-hit categories that **force `reject`**: none in V1 (reject is reserved
  for explicit operator override).
- A `RiskSourceHit` with `direct_hit=true` always wins over rule/raindrop math.

### 1.3 Error model

All 4xx/5xx responses use a single structured envelope:

```json
{
  "error": {
    "code": "string_machine_code",
    "message": "Human-readable, no stack traces, no provider tokens.",
    "category": "validation | not_found | conflict | upstream | internal",
    "retryable": false,
    "details": { "field": "to_address" },
    "trace_id": "uuid-string"
  }
}
```

- `category=validation` → HTTP 400; never reveals raw provider payloads.
- `category=not_found` → HTTP 404.
- `category=conflict` → HTTP 409 (e.g. graph not yet built).
- `category=upstream` → HTTP 502; used when Etherscan/GoPlus/DeepSeek
  return a non-2xx, time out, or return malformed data. Must include
  `details.provider` ∈ `{etherscan, goplus, deepseek}`.
- `category=internal` → HTTP 500; logged with `trace_id`. UI shows generic
  message and links the `trace_id`.

Provider failures **must never bubble up as a 500**; `connector-engineer`
wraps them as `category=upstream`. Pydantic validation errors are mapped to
`category=validation` and translated to plain English.

### 1.4 Demo provenance

When `DEMO_MODE=true` or a required key is missing for the relevant provider,
every response carrying provider-sourced data must include `data_freshness`:

```json
"data_freshness": {
  "etherscan": "demo",
  "goplus": "demo",
  "deepseek": "demo"
}
```

Valid values: `live`, `demo`, `cache`, `unavailable`. The frontend must badge
`demo` and `unavailable` so analysts never confuse it with real intelligence.

## 2. Endpoints

### 2.1 `GET /health`

Returns `{ "status": "ok", "demo_mode": bool, "version": "0.1.0" }`.

### 2.2 `POST /api/v1/screening/transactions`

Request: `ScreeningTransactionCreate`

```json
{
  "chain_id": "1",
  "asset": "USDC",
  "direction": "outbound",
  "from_address": "0x...",
  "to_address": "0x...",
  "amount": 9500,
  "customer_id": "optional",
  "team_id": "optional",
  "tx_hash": "optional 0x...66",
  "timestamp": 1730000000
}
```

Response: `ScreeningResponse`, fields per `services/api/app/domain/models.py`.
**Acceptance rules:**

- `risk_score` is the final score (0–100).
- `disposition` MUST equal `hold_for_manual_review` whenever any `source_hits`
  entry has `direct_hit=true` and `category` ∈ direct-hit list above.
- `pattern_signals`, `source_hits`, `evidence_summary`, `recommended_actions`
  are always populated arrays (may be empty, never null).
- `data_freshness` is required.

### 2.3 Investigations

- `POST /api/v1/investigations` → `InvestigationStatus`.
- `GET /api/v1/investigations` → list of `InvestigationStatus`.
- `GET /api/v1/investigations/{id}` → `InvestigationStatus`.
- `GET /api/v1/investigations/{id}/graph` → `InvestigationGraph`.
  - 409 with `category=conflict` if graph not ready.
- `GET /api/v1/investigations/{id}/risk` → `RiskResponse`.
  - 409 with `category=conflict` if risk not ready.
- `POST /api/v1/investigations/{id}/reports` → `ReportResponse`.

### 2.4 Watchlist

#### 2.4.1 `GET /api/v1/watchlists`

Returns `list[WatchlistEntry]`.

#### 2.4.2 `POST /api/v1/watchlists`

Upserts a single entry. Request: `WatchlistEntry`.

```json
{
  "address": "0x...",
  "label": "OFAC SDN Tornado.Cash demo",
  "category": "ofac",
  "severity": "critical",
  "notes": "optional"
}
```

Validation:

- `category` is freeform string, but only `category` ∈ direct-hit list will
  produce a forced `hold_for_manual_review`.
- `severity` ∈ `risk_level`.

#### 2.4.3 `POST /api/v1/watchlists/import` (Day-1 deliverable for `risk-intel-engineer`)

Bulk import. Request:

```json
{
  "format": "csv | json",
  "payload": "raw string (CSV text or JSON array text)",
  "default_category": "manual",
  "default_severity": "high",
  "replace": false
}
```

CSV schema (header REQUIRED): `address,label,category,severity,notes`.
JSON schema: array of `WatchlistEntry` objects (extra fields ignored).

Response:

```json
{
  "imported": 12,
  "updated": 3,
  "skipped": 1,
  "errors": [
    { "row": 5, "reason": "invalid address" }
  ],
  "direct_hit_count": 4
}
```

`replace=true` clears all current watchlist entries before importing; this
should only be used by operators, never auto-triggered by demo flows.

### 2.5 Screening event listing

`GET /api/v1/screening/events` → list of `ScreeningResponse` (most recent first).

## 3. Direct-hit policy (canonical)

A `source_hits` entry triggers direct-hit semantics when **all** of these are
true:

1. `direct_hit == true`.
2. `category` is one of:
   - `ofac`
   - `sanctions`
   - `pep`
   - `circle_blacklist`
   - `tether_blacklist`
   - `stablecoin_blacklist`
3. `address` matches `from_address` for inbound screening, or `to_address` for
   outbound screening, or any non-root graph node within `depth=1` of the root
   investigation target.

When triggered:

- `risk_level := critical`.
- `disposition := hold_for_manual_review`.
- `recommended_actions` MUST include `"Manual compliance review required."` as
  the first item.
- The report MUST surface the source hit before any rule/raindrop reasoning.

Pattern-only signals (no direct-hit) max out at `disposition=review`.

## 4. Demo vs production switching

- `DEMO_MODE=true` → all connectors return deterministic demo data. Reports
  must include a `Generated in demonstration mode.` banner.
- `DEMO_MODE=false` with missing provider key for a given provider → that
  provider becomes `unavailable` in `data_freshness`; other providers continue
  operating.
- The UI must never describe `demo` or `unavailable` provider hits as real
  intelligence.

## 5. Sign-off matrix

| Section                              | Owner                  | Reviewer              |
| ------------------------------------ | ---------------------- | --------------------- |
| Endpoint surface (this file)         | `aml-architect`        | n/a                   |
| Direct-hit list                      | `aml-architect`        | `risk-logic-reviewer` |
| Error model                          | `aml-architect`        | `risk-logic-reviewer` |
| Demo provenance                      | `aml-architect`        | `risk-logic-reviewer` |
| Watchlist import DTO                 | `aml-architect`        | `risk-logic-reviewer` |
| Implementation in `domain/models.py` | `risk-intel-engineer`  | `aml-architect`       |
| Implementation in `app/main.py`      | `aml-architect`        | `risk-logic-reviewer` |
| Connector error mapping              | `connector-engineer`   | `aml-architect`       |

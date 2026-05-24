# V1 API Contract (frozen by `aml-architect`)

Status: **Frozen for Day 1 / Day 2 implementation.** Changes require an
`aml-architect` amendment plus a `risk-logic-reviewer` verdict.

All endpoints are versioned under `/api/v1`. The API is local-first, CORS-gated,
and intended for a single Cregis risk operator host.

## 1. Conventions

### 1.1 Identifiers and assets

- `chain_id` is a numeric string. Ethereum mainnet (`"1"`) has built-in token metadata; other EVM chains require `token_address` for ERC-20 screening.
- `asset` is an uppercase asset symbol string, not a closed enum. Built-in Ethereum mainnet assets: `"ETH"`, `"USDT"`, `"USDC"`, `"DAI"`, `"WETH"`, `"WBTC"`. Other ERC-20 assets require `token_address`.
- `asset_type` is optional and can be `"native"` or `"erc20"`.
- `token_address` is optional for built-in Ethereum mainnet tokens and required for custom ERC-20 assets.
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
  "asset_type": "erc20",
  "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
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

For an already-on-chain transaction, the request may provide only `tx_hash` and
optional operator metadata. The backend resolves `from_address`, `to_address`,
`amount`, `asset`, `asset_type`, and `token_address` from Etherscan before
running screening:

```json
{
  "chain_id": "1",
  "tx_hash": "0x..."
}
```

ERC-20 transactions are decoded from receipt `Transfer` logs and token metadata
is read through Etherscan proxy `eth_call` where available.

Response: `ScreeningResponse`, fields per `services/api/app/domain/models.py`.
**Acceptance rules:**

- `risk_score` is the final score (0–100).
- `disposition` MUST equal `hold_for_manual_review` whenever any `source_hits`
  entry has `direct_hit=true` and `category` ∈ direct-hit list above.
- Screening context graph is lightweight: from-address and to-address are each
  expanded to at most 2 hops and 6 recent transactions per address.
- Screening may emit `one_hop_risky_exposure`, `two_hop_risky_exposure`, and
  `short_time_repeated_transfers` pattern signals when the bounded context graph
  supports those conclusions.
- `source_hits` in a screening response represent transaction-party or provider
  hits. Direct-hit rows discovered only in 1-hop or 2-hop context are surfaced as
  exposure `pattern_signals` so they do not masquerade as a direct hit on the
  proposed transaction parties.
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
  "source": "ofac_sdn",
  "source_version": "2026-05-23",
  "category": "ofac",
  "severity": "critical",
  "evidence": "OFAC SDN address match.",
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
  "default_source": "manual_import",
  "default_source_version": "",
  "replace": false
}
```

CSV schema (header REQUIRED): `address,label,source,source_version,category,severity,evidence,notes`.
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
3. `address` matches a screening party or a high-risk node inside the bounded
   screening context graph. Screening exposure evidence is limited to at most
   two hops and must cite a `source_hit` or `pattern_signal`.

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

## 5. Pruned StorageAdapter methods (2026-05-16)

The following abstract methods on `StorageAdapter` were deleted during
round-one acceptance cleanup. None have a caller in
`services/api/app/services/` or `services/api/app/main.py`.

| Method | Was in | Rationale |
|--------|--------|-----------|
| `add_risk_source_hit` | `base.py:117` | No caller; Karpathy §2 |
| `list_risk_source_hits` | `base.py:122` | No caller; Karpathy §2 |
| `add_pattern_signal` | `base.py:133` | No caller; Karpathy §2 |
| `list_pattern_signals` | `base.py:138` | No caller; Karpathy §2 |
| `add_network_metric` | `base.py:149` | No caller; Karpathy §2 |
| `list_network_metrics` | `base.py:154` | No caller; Karpathy §2 |
| `add_ai_report` | `base.py:161` | No caller; Karpathy §2 |
| `list_ai_reports` | `base.py:166` | No caller; Karpathy §2 |
| `append_audit_log` | `base.py:173` | No caller; Karpathy §2 |
| `list_audit_logs` | `base.py:184` | No caller; Karpathy §2 |
| `get_screening_event` | `base.py:78` | GET endpoint not wired in `main.py` |

When a real endpoint ships that needs one of these, it should be added back
in the same PR that wires the endpoint.

### Approvals recorded

- **R1+R3+R4 fix** (qa-devops-engineer): Approved. `python-dotenv==1.2.1`, `# requires Python >= 3.11` header, README Requirements section, boot script version check.
- **R2 fix** (web-workbench-engineer): Approved. Pin `"latest"` to resolved versions, commit `package-lock.json`.
- **Prune list** (db-storage-engineer): Approved. Delete all 11 methods from `base.py`, `memory.py`, and the full `postgres.py` file (Option A).
- **PostgresStore**: Option A approved — delete `services/api/app/storage/postgres.py`. The SQL schema in `docs/database/schema.sql` remains as the contract. When V1 actually needs persistence, write the adapter then.

## 6. Sign-off matrix

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

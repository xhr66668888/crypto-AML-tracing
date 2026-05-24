# Known Limitations — V1

**Frozen**: 2026-05-16
**Owner**: `aml-architect`

This document lists capabilities that V1 does **NOT** support. These are not bugs; they are out of scope for the initial release.

---

## 1. No Real PEP Commercial Library

V1 uses a local watchlist with manually imported entries. There is no integration with a commercial PEP (Politically Exposed Persons) database such as Dow Jones, World-Check, or ComplyAdvantage.

**Impact**: PEP screening is limited to addresses manually added to the local watchlist with `category=pep`.

**Mitigation**: The watchlist import endpoint accepts CSV/JSON, so PEP data can be bulk-imported if provided externally.

---

## 2. No Circle/Tether Official Blacklist Sync

V1 does not automatically sync with Circle's USDC blacklist or Tether's USDT blacklist. Stablecoin blacklist entries must be manually imported into the local watchlist.

**Impact**: Real-time stablecoin blacklist enforcement is not available. Analysts must manually maintain the watchlist.

**Mitigation**: The `category` field supports `circle_blacklist`, `tether_blacklist`, and `stablecoin_blacklist`. Entries with these categories trigger `direct_hit=True` and `hold_for_manual_review`.

---

## 3. Limited Multi-Chain Support

V1 now supports a curated set of EVM chains via Etherscan API V2:

- Ethereum Mainnet (`1`)
- BNB Smart Chain (`56`)
- Polygon (`137`)
- Arbitrum One (`42161`)
- Optimism (`10`)
- Base (`8453`)

There is still no support for non-EVM networks such as Tron/TRC-20.

**Impact**: Cross-chain fund tracing is limited to the configured EVM chain selected per investigation or screening request. Bridge attribution is not automated.

---

## 4. No Real ML Training

The Raindrop AML scorer (`RaindropAmlScorer`) uses a deterministic, rule-based feature scoring algorithm. There is no trained neural network, no PyTorch/PyG model, and no GPU inference.

**Impact**: The `raindrop_score` is derived from hand-tuned heuristics (centrality, risk tags, temporal burstiness, value dispersion, graph depth). It does not learn from labelled data.

**Future path**: The `ml/` module is structured to accept a PyTorch/PyG model that replaces the internals of `predict()` while keeping the same `(InvestigationGraph) -> RaindropResult` signature. Feature schema version is tracked in `ml/features.py`.

---

## 5. No Enterprise Permissions / Approval Flows / Audit Backend

V1 is a local-first tool with no authentication, authorization, role-based access control, or approval workflows.

**Not supported**:
- User login / SSO / LDAP
- Role-based permissions (analyst, reviewer, admin)
- Multi-step approval workflows (e.g., analyst screens → reviewer approves → compliance officer signs off)
- Persistent audit log (the in-memory store has `append_audit_log` but it is lost on restart)
- Webhook notifications
- S3/blob storage for reports

**Impact**: All data is in-memory and lost on process restart. There is no multi-user support.

**Mitigation**: The `StorageAdapter` interface is designed for a future `PostgresStore` swap. The `audit_logs` table schema exists in `docs/database/schema.sql`.

---

## 6. No Real-Time Provider Streaming

V1 fetches Etherscan and GoPlus data on-demand per investigation. There is no:

- WebSocket connection to Etherscan/GoPlus
- Mempool monitoring
- Real-time block streaming
- Push notifications from providers

**Impact**: Transaction data is only as fresh as the last API call. There is no real-time alerting.

---

## 7. No OFAC/SDN Official Feed Integration

V1 does not automatically import or sync with the official OFAC SDN (Specially Designated Nationals) list, EU sanctions list, or UN sanctions list.

**Impact**: Sanctions screening depends entirely on manually imported watchlist entries.

---

## 8. No Report Scheduling or Automated Screening

V1 does not support:

- Scheduled batch screening
- Cron-based report generation
- Automated alerts (email, Slack, webhook)
- Queue-based background processing

All operations are synchronous API calls.

---

## 9. Limited Token Transfer Graph Tracing

V1 can trace ERC-20 transfers through Etherscan's `tokentx` endpoint for configured token contracts or a manually supplied `token_contract_address`.

**Impact**: ERC-721/ERC-1155 transfers, DEX swaps, bridge events, and protocol-specific decoded actions are not yet modeled as first-class graph events.

---

## 10. No Compliance Report Templates for Jurisdictions

V1 generates a single English report format. There are no jurisdiction-specific templates (e.g., SAR/STR formats for US, EU, or APAC regulators).

---

## Summary Table

| Capability | V1 Status |
|---|---|
| Real PEP commercial library | Not supported |
| Circle/Tether official blacklist sync | Not supported |
| Multi-chain (curated EVM chains) | Supported |
| Real ML training / GPU inference | Not supported |
| Enterprise permissions / approval flows | Not supported |
| Persistent audit backend | Schema ready, not wired |
| Real-time provider streaming | Not supported |
| OFAC/SDN official feed sync | Not supported |
| Scheduled batch screening | Not supported |
| ERC-20 token transfer tracing | Supported with configured/custom contracts |
| Jurisdiction-specific report templates | Not supported |

---

## Code-quality limitations (round-two acceptance audit, 2026-05-16)

Round-one Karpathy §2 cleanup removed ~1,200 lines of speculative/dead code
across `PostgresStore`, `raindrop_aml.py`, the `language=` plumbing, and the
`isinstance(..., tuple)` compatibility branches. The round-two re-audit found
**3 hard blockers and 5 §2/§3 cleanups still open** — orphan import in
`storage/factory.py`, real-shaped secrets in `.env.example`, the hard-coded
"Demo data" footer, dead `ReportRequest.language` field, 9 ruff F401/F841
hits, the deleted empty `services/api/app/api/` package, dead `DATABASE_URL` lines in
`.env.example`, and an incorrect "approved" summary in
[`docs/acceptance-review.md`](acceptance-review.md).

The per-agent fix list, exit criteria, and reproducers live in
[`docs/acceptance-review-round-two.md`](acceptance-review-round-two.md). The
quality bar that codifies these rules lives at
[`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md).

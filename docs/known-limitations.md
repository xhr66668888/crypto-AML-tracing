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

## 2. Circle/Tether RPC Coverage Is Ethereum-Only

V1 checks Circle USDC and Tether USDT blacklist status through Ethereum
JSON-RPC during pre-transaction screening. It does not yet cover non-Ethereum
deployments such as Tron, Avalanche, Base, Arbitrum, or Polygon.

**Impact**: USDC/USDT screening on Ethereum can generate direct-hit evidence,
but non-Ethereum stablecoin blacklist enforcement is not available.

**Mitigation**: Use a stable private `ETHEREUM_RPC_URL` for production
Ethereum checks. Non-Ethereum blacklist entries can still be manually imported
into the local watchlist with `circle_blacklist`, `tether_blacklist`, or
`stablecoin_blacklist` categories.

---

## 3. No Multi-Chain Support

V1 supports Ethereum mainnet only (chain_id `"1"`). There is no support for:

- Tron (TRC-20 USDT)
- BNB Smart Chain (BEP-20)
- Polygon
- Arbitrum / Optimism
- Any other EVM or non-EVM chain

**Impact**: Cross-chain fund tracing is not possible. Addresses that move funds through bridges or other chains will have incomplete graphs.

**Mitigation**: The `chain_id` field is present in all models and can be extended in future versions.

---

## 4. Screening Context Is Lightweight, Not Full Provenance

Pre-transaction screening expands both `from_address` and `to_address`, but only
to at most 2 hops and 6 recent transactions per address. This is intentionally
bounded for fast allow/review/hold decisions.

**Impact**: A clean screening context does not prove complete fund provenance.
It only means no high-risk evidence was found inside the bounded context and
configured provider/watchlist checks.

**Mitigation**: Use the deeper investigation workflow for post-transaction or
case-level tracing.

---

## 5. No Real ML Training

The Raindrop AML scorer (`RaindropAmlScorer`) uses a deterministic, rule-based feature scoring algorithm. There is no trained neural network, no PyTorch/PyG model, and no GPU inference.

**Impact**: The `raindrop_score` is derived from hand-tuned heuristics (centrality, risk tags, temporal burstiness, value dispersion, graph depth). It does not learn from labelled data.

**Future path**: The `ml/` module is structured to accept a PyTorch/PyG model that replaces the internals of `predict()` while keeping the same `(InvestigationGraph) -> RaindropResult` signature. Feature schema version is tracked in `ml/features.py`.

---

## 6. No Enterprise Permissions / Approval Flows / Audit Backend

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

## 7. No Real-Time Provider Streaming

V1 fetches Etherscan and GoPlus data on-demand per investigation. There is no:

- WebSocket connection to Etherscan/GoPlus
- Mempool monitoring
- Real-time block streaming
- Push notifications from providers

**Impact**: Transaction data is only as fresh as the last API call. There is no real-time alerting.

---

## 8. Partial OFAC Official Feed Integration

V1 can manually or weekly sync OFAC SDN and OFAC Consolidated digital-currency
address rows into the local persistent watchlist. UN, UK, EU, and other
name/entity sanctions lists are not connected yet.

**Impact**: Sanctions wallet screening covers OFAC digital-currency addresses
and manually imported rows, but does not yet perform name/KYC sanctions
screening.

---

## 9. No Report Scheduling or Automated Screening

V1 does not support:

- Scheduled batch screening
- Cron-based report generation
- Automated alerts (email, Slack, webhook)
- Queue-based background processing

All operations are synchronous API calls.

---

## 10. Partial Token Transfer (ERC-20) Graph Tracing

Pre-transaction screening can build ERC-20 context graphs through Etherscan's
`tokentx` API when the asset resolves to a token contract. Built-in Ethereum
mainnet metadata is available for USDT, USDC, DAI, WETH, and WBTC; custom
ERC-20 assets require `asset_type="erc20"` and `token_address`.

**Impact**: ERC-20 screening has token transfer context for the screened
contract, but deep investigation endpoints still default to native ETH graph
expansion unless a future endpoint explicitly accepts token context.

**Mitigation**: Use the screening API for token transfer decisions. Add a
token-aware investigation API before claiming full ERC-20 investigation
coverage.

---

## 11. No Compliance Report Templates for Jurisdictions

V1 generates a single English report format. There are no jurisdiction-specific templates (e.g., SAR/STR formats for US, EU, or APAC regulators).

---

## Summary Table

| Capability | V1 Status |
|---|---|
| Real PEP commercial library | Not supported |
| Circle/Tether official blacklist sync | Ethereum RPC supported |
| Multi-chain (Tron, BSC, Polygon) | Not supported |
| Complete fund provenance in screening | Not supported |
| Real ML training / GPU inference | Not supported |
| Enterprise permissions / approval flows | Not supported |
| Persistent audit backend | Schema ready, not wired |
| Real-time provider streaming | Not supported |
| OFAC/SDN official feed sync | OFAC address sync supported |
| Scheduled batch screening | Not supported |
| ERC-20 token transfer tracing | Screening supported; investigations not token-aware |
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

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

## 9. No Token Transfer (ERC-20) Graph Tracing

V1 traces ETH (native) transfers via Etherscan's `txlist` API. ERC-20 token transfers (USDT, USDC) are not traced at the graph level.

**Impact**: The `asset` field in screening is used for threshold analysis only. The transaction graph is built from ETH transfers, not token transfers.

---

## 10. No Compliance Report Templates for Jurisdictions

V1 generates a single English report format. There are no jurisdiction-specific templates (e.g., SAR/STR formats for US, EU, or APAC regulators).

---

## Summary Table

| Capability | V1 Status |
|---|---|
| Real PEP commercial library | Not supported |
| Circle/Tether official blacklist sync | Not supported |
| Multi-chain (Tron, BSC, Polygon) | Not supported |
| Real ML training / GPU inference | Not supported |
| Enterprise permissions / approval flows | Not supported |
| Persistent audit backend | Schema ready, not wired |
| Real-time provider streaming | Not supported |
| OFAC/SDN official feed sync | Not supported |
| Scheduled batch screening | Not supported |
| ERC-20 token transfer tracing | Not supported |
| Jurisdiction-specific report templates | Not supported |

---

## Code-quality limitations (round-one acceptance audit, 2026-05-16)

These are not feature gaps — they are open Karpathy-violation cleanups that
the project director flagged at acceptance. They block release and are
tracked individually in [`docs/acceptance-review.md`](acceptance-review.md)
and [`docs/release-checklist.md § 11`](release-checklist.md). Listed here so
every contributor sees them in the limitations document too.

| # | Area | Issue | Owner |
|---|---|---|---|
| C1 | `services/api/requirements.txt` | `python-dotenv==1.2.2` does not exist on PyPI; install fails. | `qa-devops-engineer` |
| C2 | `services/api/app/domain/models.py` etc. | uses `from datetime import UTC` (Python ≥ 3.11) but README does not state this. | `qa-devops-engineer` + `aml-architect` |
| C3 | `apps/web/package.json` | every dependency pinned to `"latest"`; non-reproducible build. | `web-workbench-engineer` |
| C4 | `services/api/app/ml/raindrop_aml.py` | dead duplicate of `raindrop_scorer.py`; not imported anywhere. | `raindrop-ml-engineer` |
| C5 | `services/api/app/domain/scoring.py:66-70` | dead `isinstance(result, tuple)` branch supporting the dead duplicate above. | `raindrop-ml-engineer` |
| C6 | `services/api/app/storage/postgres.py` | 442 lines with `NotImplementedError` and `TODO`s; never instantiated. | `db-storage-engineer` |
| C7 | `services/api/app/storage/base.py` + `memory.py` | many `@abstractmethod`s (`add_risk_source_hit`, `add_pattern_signal`, `add_network_metric`, `add_ai_report`, `append_audit_log`, …) have no production caller. | `aml-architect` + `db-storage-engineer` |
| C8 | `services/api/app/connectors/etherscan.py` | `get_internal_transactions` is tested but not used in production. | `connector-engineer` |
| C9 | `services/api/app/domain/patterns.py` | unused `import math`; `_build_adjacency` is called but the returned `adj` is never read by its consumer. | `graph-pattern-engineer` |
| C10 | `services/api/app/domain/scoring.py` | redundant disposition branch + commented-out alternative formula. | `risk-intel-engineer` |
| C11 | `services/api/app/services/reporting.py` | `DeepSeekReporter` "backward-compatible alias" with no V0; `language=` parameter never consumed. | `report-engineer` |
| C12 | `services/api/app/main.py:135-212` | watchlist CSV/JSON import paths repeat ~30 lines. | `risk-intel-engineer` |
| C13 | `apps/web/src/App.tsx:11` | `connectionStatus` state; setter never called; `ConnectionIndicator` always returns `null`. | `web-workbench-engineer` |

Closing all of these moves the project from `approved-with-changes` to
`approved`. The skill that codifies the quality bar lives at
[`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md).

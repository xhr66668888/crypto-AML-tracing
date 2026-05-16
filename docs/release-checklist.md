# V1 Release Checklist

**Frozen**: 2026-05-16
**Owner**: `aml-architect`
**Sign-off required before release.**

---

## 1. API Contract

- [ ] All endpoints documented in `docs/contract-changelog.md`
- [ ] All request/response models have Pydantic schemas in `domain/models.py`
- [ ] `RaindropAmlScorer.predict(graph)` signature frozen
- [ ] `DIRECT_HIT_CATEGORIES` frozen in `domain/models.py`
- [ ] `main.py` imports from `app.ml.raindrop_scorer` (frozen interface)

## 2. Direct-Hit Policy

- [ ] `ofac` → forces `hold_for_manual_review`
- [ ] `pep` → forces `hold_for_manual_review`
- [ ] `sanctions` → forces `hold_for_manual_review`
- [ ] `sanctioned` → forces `hold_for_manual_review`
- [ ] `circle_blacklist` → forces `hold_for_manual_review`
- [ ] `tether_blacklist` → forces `hold_for_manual_review`
- [ ] `stablecoin_blacklist` → forces `hold_for_manual_review`
- [ ] Direct-hit overrides any behavioural score (even score=0)
- [ ] Tests verify: `test_screening_direct_source_hit_forces_manual_hold`, `TestDirectHitIntegration`

## 3. Evidence Integrity

- [ ] Every risk conclusion references `source_hit`, `pattern_signal`, or `evidence`
- [ ] Reports do not invent facts (test: `test_no_invented_evidence`)
- [ ] Reports explicitly state "No evidence found" when empty (test: `test_report_states_no_evidence`)
- [ ] Demo data labelled as `demo` in API responses (`source: "demo"` in connector output)
- [ ] Demo data labelled as `DEMONSTRATION DATA` in reports (test: `test_demo_header_present`)

## 4. Module Boundaries

- [ ] `connectors/` — no imports from `domain/`, `ml/`, `services/`, `storage/`
- [ ] `domain/` — imports from `connectors/` only (GoPlus, Etherscan clients)
- [ ] `ml/` — imports from `domain/models.py` only
- [ ] `services/` — imports from `domain/`, `connectors/`, `storage/base`
- [ ] `storage/` — imports from `domain/models.py` only
- [ ] `main.py` — entry point, imports from all modules (allowed)
- [ ] No circular imports

## 5. .env Configuration

- [ ] `DEMO_MODE` — documented, defaults to `true`
- [ ] `CHAIN_ID` — documented, defaults to `1`
- [ ] `ETHERSCAN_API_KEY` — documented, empty default
- [ ] `ETHERSCAN_BASE_URL` — documented
- [ ] `GOPLUS_TOKEN` — documented
- [ ] `DEEPSEEK_API_KEY` — documented, empty default
- [ ] `DEEPSEEK_MODEL` — documented
- [ ] `DEEPSEEK_BASE_URL` — documented
- [ ] `CORS_ORIGINS` — documented
- [ ] `MAX_STABLE_NODES` — documented, default 75
- [ ] `MAX_EXPERIMENTAL_NODES` — documented, default 160
- [ ] `ETHERSCAN_TIMEOUT_SECONDS` — documented, default 10
- [ ] `GOPLUS_TIMEOUT_SECONDS` — documented, default 10
- [ ] `DEEPSEEK_TIMEOUT_SECONDS` — documented, default 30
- [ ] `CONNECTOR_MAX_RETRIES` — documented, default 2
- [ ] `VITE_API_BASE` — documented, frontend env
- [ ] `DATABASE_URL` — documented (optional, commented out)

## 6. Tests

- [ ] `PYTHONPATH=services/api pytest -q` passes (0 failures)
- [ ] Direct-hit override tests pass
- [ ] All 9 pattern detectors have tests
- [ ] Connector error handling tests pass (timeout, 429, 500, retry)
- [ ] Report evidence citation tests pass
- [ ] Raindrop scorer contract tests pass
- [ ] Watchlist CSV/JSON import tests pass

## 7. Frontend Build

- [ ] `cd apps/web && npm run build` succeeds
- [ ] No TypeScript errors
- [ ] No broken imports

## 8. Demo Mode

- [ ] App boots without any API keys configured
- [ ] Etherscan demo returns deterministic data
- [ ] GoPlus demo returns deterministic data
- [ ] DeepSeek demo returns local template
- [ ] All demo data includes `source: "demo"` marker
- [ ] Reports in demo mode include `DEMONSTRATION DATA` header

## 9. Documentation

- [ ] `docs/contract-changelog.md` — complete
- [ ] `docs/known-limitations.md` — complete
- [ ] `docs/release-checklist.md` — this file
- [ ] `docs/architecture.md` — accurate
- [ ] `docs/team-assignments.md` — accurate
- [ ] `README.md` — run instructions work on a clean machine
- [ ] `scripts/smoke.sh` — covers all V1 endpoints

## 10. Known Limitations Acknowledged

- [ ] No real PEP commercial library
- [ ] No Circle/Tether official blacklist sync
- [ ] No multi-chain support
- [ ] No real ML training
- [ ] No enterprise permissions/approval flows/audit backend
- [ ] All documented in `docs/known-limitations.md`

---

## Sign-off

| Agent | Role | Status | Date |
|-------|------|--------|------|
| `aml-architect` | Contract owner | FROZEN | 2026-05-16 |
| `risk-logic-reviewer` | Compliance audit | PENDING | — |

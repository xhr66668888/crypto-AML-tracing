# Pre-Transaction Screening MVP Summary

给 coworker 的简短说明：本轮工作把项目从 “general AML tracing demo” 调整成一个更清晰的 **Pre-Transaction Screening + Address Analysis** MVP。

## Product Split

### 1. Pre-Transaction Screening

用途：交易发出前，或入账 credit 前，判断一个 counterparty address 是否可以继续处理。

Current behavior:

- `outbound`: 客户从 Cregis 转出，筛查 recipient address。
- `inbound`: 外部地址转入 Cregis，筛查 source address。
- 输入不再使用 transaction hash，因为 hash 通常在交易广播后才存在。
- 返回 `allow / review / hold_for_manual_review`、risk score、source hits、pattern signals、evidence summary、recommended actions。

Main endpoint:

```text
POST /api/v1/screening/pre-transactions
```

Key request fields:

```text
direction, chain_id, asset, asset_type, token_address, counterparty_address, amount, customer_id, team_id
```

### 2. Address Analysis

用途：交易发生后或调查阶段，对 address / transaction hash 做 graph screening。

Current behavior:

- 支持输入 Ethereum address。
- 支持输入 transaction hash。
- 生成 graph、risk findings、source hits、pattern signals、report evidence。

Main endpoint:

```text
POST /api/v1/investigations
```

## Implemented Tasks

- PRD / risk policy: defined direct-hit hold, review thresholds, degraded-provider review behavior.
- OFAC watchlist: added local ingestion/sync path and evidence fields.
- Stablecoin blacklist: added Circle USDC and Tether USDT blacklist checks through Ethereum RPC.
- Provider layer: normalized provider outputs into source hits / pattern signals.
- ERC-20 support: expanded from ETH/USDT/USDC enum to ETH mainnet ERC-20 assets, including DAI, WETH, WBTC, and custom token address.
- Lightweight context graph: added bounded 2-hop context for fast screening evidence.
- Decision engine: separated numeric risk score from business disposition.
- Frontend UX: split pre-transaction screening from address analysis.

## Important Code Changes

Backend:

- `services/api/app/domain/models.py`
  - Added `PreTransactionScreeningCreate`.
  - Screening request now requires `counterparty_address`.
  - `tx_hash`, `from_address`, and `to_address` are no longer valid pre-transaction inputs.

- `services/api/app/services/screening.py`
  - Screening now evaluates only the counterparty address.
  - `outbound` maps counterparty to recipient.
  - `inbound` maps counterparty to source.
  - Graph context is used as supporting evidence, not as the primary product output.

- `services/api/app/main.py`
  - Added `POST /api/v1/screening/pre-transactions`.
  - Kept `/api/v1/screening/transactions` as compatibility alias using the same new contract.

- `services/api/app/domain/patterns.py`
  - Pattern subjects now follow the actual counterparty for inbound/outbound screening.

Frontend:

- `apps/web/src/components/ScreeningPanel.tsx`
  - Removed tx hash from pre-transaction form.
  - Added recipient/source address input based on workflow.
  - Calls `/api/v1/screening/pre-transactions`.

- `apps/web/src/components/InvestigationPanel.tsx`
  - Repositioned as Address Analysis.
  - Keeps address / transaction hash graph workflow.

- `apps/web/src/App.tsx`
  - Navigation now separates Pre-Transaction Screening, Watchlist, and Address Analysis.

## Verification

Latest checks passed:

```text
Backend tests: 271 passed
Frontend build: passed
Smoke tests: 24/24 passed
```

Known note:

- `npm run build` still shows a Vite chunk-size warning. It is not a functional failure.

# Pre-Transaction Scanning Product Plan

## Summary

This project will first focus on a usable pre-transaction scanning product.
Before funds are released or accepted, the system receives a proposed
transaction and returns a decision, risk score, risk level, source-backed
evidence, and recommended actions.

The immediate product question is:

> Can this proposed transaction be allowed now? If not, what evidence supports
> review or hold?

This plan intentionally deprioritizes deep post-transaction investigation and
full Raindrop model presentation for the first product milestone.

## Product Shape

The pre-transaction scanner should evaluate transaction context, not only a
single address.

Expected input:

```text
chain_id
direction: inbound / outbound
from_address
to_address
asset_type: native / erc20
token_address optional
asset_symbol
amount
customer_id optional
tx_hash optional
```

Expected output:

```text
final_risk_score
final_risk_level
disposition: allow / review / hold_for_manual_review
source_hits
pattern_signals
recommended_actions
evidence_summary
```

## Risk Policy

Risk policy should be configurable and iterated over time. It should not be
hardcoded inside the scoring algorithm.

Example policy rules:

```text
category=ofac -> hold_for_manual_review
category=sanctions -> hold_for_manual_review
category=circle_blacklist -> hold_for_manual_review
category=tether_blacklist -> hold_for_manual_review
category=pep -> review or hold_for_manual_review, depending on policy
score>=85 -> hold_for_manual_review
score>=35 -> review
provider_timeout -> degraded_review
```

Default principles:

- Direct hits take priority over behavioral scores.
- OFAC, sanctions, stablecoin blacklist, and other direct-hit categories force
  manual hold.
- Provider hits from GoPlus or later AML providers are evidence, not final
  truth by themselves.
- Behavioral patterns such as threshold structuring, dusting, and recent risky
  exposure are supporting signals.
- Raindrop scoring remains a separate algorithm workstream and does not block
  the pre-transaction MVP.
- Every risk conclusion must be traceable to a source hit, pattern signal, or
  evidence row.

## Task Split

### 1. PRD and Risk Policy

Define the pre-transaction product boundary and business decision rules.

Deliverables:

- Inbound and outbound decision logic.
- `allow`, `review`, and `hold_for_manual_review` trigger conditions.
- Amount thresholds for ETH, USDT, USDC, and later ERC-20 defaults.
- Demo-data wording and compliance boundaries.
- Updated PRD positioning the product as a pre-transaction scanning MVP.

### 2. Watchlist and Public Dataset

Build local risk-list ingestion and synchronization.

First data sources:

- OFAC SDN and Consolidated Sanctions data.
- UN sanctions list.
- UK Sanctions List.
- OpenSanctions sanctions and PEP data.
- Circle USDC blacklist on-chain checks.
- Tether USDT blacklist on-chain checks.

Requirements:

- Store `source`, `source_version`, `category`, `severity`, and `evidence`.
- Support manual CSV/JSON import.
- Support manual sync first, then scheduled daily sync.
- Treat OpenSanctions as an aggregator, not the only official source.

### 3. Provider Layer

Keep GoPlus, but position it as a Web3 security provider rather than a full AML
investigation provider.

Candidate AML providers to evaluate:

- Chainalysis
- TRM Labs
- Elliptic
- Scorechain
- Merkle Science
- Crystal Intelligence
- Crypto APIs Verify Address
- AMLBot
- CertiK SkyInsights

Deliverables:

- Provider comparison matrix.
- Unified `RiskProvider` interface.
- Provider results normalized into `source_hits`.
- One additional AML provider selected for later comparison with GoPlus.

### 4. Ethereum Asset Support

Extend pre-transaction scanning from native ETH to mainstream ERC-20 assets.

First supported assets:

- ETH
- USDT
- USDC
- DAI
- WETH

Second batch candidate:

- WBTC

Requirements:

- Do not limit the API to only the current ETH/USDT/USDC enum.
- Support `chain_id + token_address` asset identification.
- Use token metadata such as symbol, decimals, and contract address.
- Check token contract risk and stablecoin blacklist status during screening.

### 5. Lightweight Context Graph

Use bounded on-chain context for fast pre-transaction decisions. This is not a
full post-transaction tracing product.

Default limits:

- Stable mode: up to 2 hops.
- Up to 6 recent relevant transactions per address.
- Use context only to support screening evidence, not to claim complete fund
  provenance.

Signals:

- Direct hit on `from_address` or `to_address`.
- Recent interaction with high-risk addresses.
- One-hop or two-hop risky exposure.
- Amount close to review thresholds.
- Short-time repeated transfers suggesting structuring.

Disposition boundary:

- A direct sanctions/stablecoin blacklist hit on `from_address` or `to_address`
  is a `source_hits` direct hit and forces `hold_for_manual_review`.
- A sanctions/stablecoin blacklist hit discovered only in the bounded 1-hop or
  2-hop context is represented as a context exposure `pattern_signal`, not as a
  direct transaction-party source hit.
- Context exposure should normally drive `review` unless another direct party
  hit or high-score business rule applies.

### 6. Decision Engine and Scoring

Separate score calculation from business disposition.

Requirements:

- `score` represents risk intensity.
- `disposition` represents action.
- Direct hits can force hold even if the numerical score is not high.
- Provider unavailable should return degraded evidence, not silently clean.
- Demo mode should be isolated so normal addresses do not consistently score
  above 70.
- Disposition thresholds and degraded-provider handling live in a decision
  policy layer, while score calculation remains evidence-driven.
- Degraded provider signals should normally produce `review` and a retry action,
  not `allow`.

Suggested default decisions:

```text
direct sanctions/stablecoin blacklist hit -> hold_for_manual_review
PEP hit -> review or hold_for_manual_review, depending on policy
high-confidence provider illicit hit -> hold_for_manual_review or review
medium provider hit or behavioral pattern -> review
no hit and low behavioral risk -> allow
```

### 7. Frontend and Analyst UX

Shift the user experience from a general investigation page to a
pre-transaction decision console.

Core view:

- Input transaction direction, chain, asset, amount, from address, and to
  address.
- Show decision first: Allow, Review, or Hold.
- Show risk score as supporting context, not the only product output.
- Show source hits, provider hits, and pattern signals.
- Clearly label demo data versus real provider data.
- Support copy/export of the screening result.

### 8. QA and Evidence Integrity

Cover compliance invariants and acceptance tests.

Required scenarios:

- Outbound transfer to OFAC address returns `hold_for_manual_review`.
- Inbound transfer from sanctioned address returns `hold_for_manual_review`.
- USDC recipient on Circle blacklist returns `hold_for_manual_review`.
- USDT recipient on Tether blacklist returns `hold_for_manual_review`.
- Clean ETH transfer does not default to high risk.
- GoPlus unavailable returns degraded evidence.
- ERC-20 token payload completes screening.
- Demo reports clearly state demonstration data.

## Implementation Order

1. Update PRD and risk policy for pre-transaction scanning.
2. Fix demo scoring so normal addresses are not systematically high risk.
3. Strengthen watchlist direct-hit ingestion and evidence fields.
4. Extend screening input for ERC-20 token metadata.
5. Add Circle and Tether blacklist checks.
6. Abstract the provider layer while keeping GoPlus.
7. Update frontend to a pre-transaction decision workflow.
8. Add tests and smoke coverage.

## Test Plan

Run the existing project acceptance commands:

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm run build
bash scripts/smoke.sh
```

Add targeted tests for:

- Direct-hit categories forcing hold.
- Configurable PEP review or hold behavior.
- Stablecoin blacklist checks.
- Clean-address low-risk baseline.
- Provider timeout and degraded evidence.
- ERC-20 pre-transaction payload support.

## Assumptions

- The first milestone is pre-transaction scanning, not deep post-transaction
  investigation.
- Ethereum mainnet remains the first supported chain.
- ERC-20 support starts with mainstream assets.
- Multichain support comes later: EVM chains first, then Tron, then
  Solana/Cosmos/Cardano.
- Raindrop remains a separate algorithm workstream with its current interface
  preserved.
- Risk policy is expected to change as better datasets, providers, and
  calibration data become available.

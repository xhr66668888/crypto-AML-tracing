# Architecture

## Product Shape

This project is a local AML risk operations tool for Cregis compliance and risk analysts. The first release supports Ethereum mainnet ETH/USDT/USDC. It prioritizes pre-release transfer screening, single-investigation workflows, explainable evidence, deterministic pattern analysis, and an experimental Raindrop-derived risk layer.

## Runtime Flow

1. Operator screens an inbound/outbound transfer through `POST /api/v1/screening/transactions`, or an analyst submits an address/transaction hash from the React workbench.
2. FastAPI validates the target and creates an investigation record.
3. `EtherscanClient` fetches or demo-generates transaction data.
4. `GraphBuilder` expands a bounded transaction graph to 3 stable hops or 5 experimental hops.
5. `RiskIntelAggregator` enriches graph nodes with GoPlus, local watchlist tags, and source-hit semantics for direct sanctions/PEP/stablecoin-blacklist style matches.
6. `PatternAnalyzer` detects deterministic AML patterns such as layering, aggregation, peel-chain behavior, threshold structuring, dusting, sparse-address large transfers, centrality hubs, and risk propagation.
7. `RiskScoringEngine` computes rule score, Raindrop score, final risk score, findings, top paths, disposition hints, and recommended actions.
8. `DeepSeekReporter` generates an English report when an API key is configured, or a local report otherwise.

## Module Boundaries

- `connectors`: third-party API clients and demo-mode fallbacks.
- `domain`: target validation, graph building, pattern analysis, risk intelligence, and scoring.
- `ml`: stable adapter surface for Raindrop AML scoring.
- `services`: screening, investigation orchestration, and report generation.
- `storage`: persistence boundary; currently in-memory, later PostgreSQL.
- `apps/web`: analyst workbench.

## Raindrop Placement

Raindrop is used in the experimental risk judgment layer. It must not override strong compliance evidence. The UI exposes `rule_score`, `raindrop_score`, and `final_risk_score` separately so analysts can distinguish source-backed findings from ML prioritization.

## Direct-Hit Policy

OFAC/sanctions, PEP, Circle/Tether/stablecoin blacklist, and local critical watchlist categories are direct-hit signals. They produce a high-risk label and `hold_for_manual_review` disposition even when the total behavioral score is below the normal high-risk threshold. Pattern-only signals produce review priority unless paired with source-backed evidence.

## Security Defaults

- Local service defaults to demo mode and browser-only usage.
- API keys are read from `.env` and never committed.
- DeepSeek receives full investigation context only when `DEEPSEEK_API_KEY` is configured and a report is requested.
- The API is intended to listen on localhost in production packaging unless Cregis explicitly enables network access.

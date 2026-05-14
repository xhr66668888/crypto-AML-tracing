# Architecture

## Product Shape

This project is a local Web AML tool for Cregis compliance and risk analysts. The first release supports Ethereum mainnet only. It prioritizes single-investigation workflows, explainable evidence, and an experimental Raindrop-derived risk layer.

## Runtime Flow

1. Analyst submits an address or transaction hash from the React workbench.
2. FastAPI validates the target and creates an investigation record.
3. `EtherscanClient` fetches or demo-generates transaction data.
4. `GraphBuilder` expands a bounded transaction graph to 3 stable hops or 5 experimental hops.
5. `RiskIntelAggregator` enriches graph nodes with GoPlus and local watchlist tags.
6. `RiskScoringEngine` computes rule score, Raindrop score, final risk score, findings, and top paths.
7. `DeepSeekReporter` generates an English report when an API key is configured, or a local report otherwise.

## Module Boundaries

- `connectors`: third-party API clients and demo-mode fallbacks.
- `domain`: target validation, graph building, risk intelligence, and scoring.
- `ml`: stable adapter surface for Raindrop AML scoring.
- `services`: application orchestration and report generation.
- `storage`: persistence boundary; currently in-memory, later PostgreSQL.
- `apps/web`: analyst workbench.

## Raindrop Placement

Raindrop is used in the experimental risk judgment layer. It must not override strong compliance evidence. The UI exposes `rule_score`, `raindrop_score`, and `final_risk_score` separately so analysts can distinguish source-backed findings from ML prioritization.

## Security Defaults

- Local service defaults to demo mode and browser-only usage.
- API keys are read from `.env` and never committed.
- DeepSeek receives full investigation context only when `DEEPSEEK_API_KEY` is configured and a report is requested.
- The API is intended to listen on localhost in production packaging unless Cregis explicitly enables network access.

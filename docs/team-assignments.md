# Team Assignments

The project is split so different programmers or AI models can work independently without stepping on each other.

## Principal Architect / Project Commander

Owns architecture decisions, API contracts, data contracts, review standards, and integration. This role approves cross-module schema changes and keeps implementation aligned with the AML product goal.

## Programmer A: Backend Data Engineering

Owns `services/api/app/connectors`, provider error handling, rate limits, caching, and the future PostgreSQL repository adapter. Deliverables: reliable Etherscan/GoPlus integration, deterministic demo fixtures, and connector tests.

## Programmer B: Graph / Pattern Algorithm Engineering

Owns `services/api/app/domain/graph_builder.py`, `services/api/app/domain/patterns.py`, and graph feature extraction. Deliverables: bounded 3-hop stable tracing, 5-hop experimental tracing, pruning strategy, path extraction, deterministic Pattern Analysis, network metrics, and performance tests.

## Programmer C: Raindrop ML Engineering

Owns `services/api/app/ml` and `services/ml/raindrop_aml`. Deliverables: AML feature tensor builder, Raindrop model port, training/evaluation pipeline, metrics, model versioning, CPU inference, optional GPU training.

## Programmer D: Risk Intelligence Engineering

Owns `risk_intel`, watchlist semantics, public label ingestion, source-hit semantics, direct-hit policy, risk taxonomy, severity weights, and rule-score calibration. Deliverables: explainable findings, allow/block list behavior, OFAC/PEP/stablecoin blacklist handling, and taxonomy docs.

## Programmer E: Frontend Engineering

Owns `apps/web`. Deliverables: investigation workflow, graph exploration, evidence review, node details, report preview, accessibility, responsive layout, and Playwright tests.

## Programmer F: AI Report Engineering

Owns `services/api/app/services/reporting.py` and Copilot response policy. Deliverables: DeepSeek prompts, report schema, risk explanation behavior, context compression, audit trail, and report quality tests.

## Programmer G: QA / Security / DevOps

Owns `docker-compose.yml`, CI, environment templates, security checks, test fixtures, release packaging, and local deployment documentation.

## Coordination Rules

- Each programmer changes only their owned module unless the Principal Architect approves a contract change.
- Cross-module changes start with API/schema updates and tests.
- Raindrop outputs are advisory until validated with Cregis cases.
- Report generation must not hide the original evidence or raw scores.

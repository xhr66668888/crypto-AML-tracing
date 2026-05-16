# Raindrop Migration Guide

## Overview

The Raindrop AML risk layer provides an ML-derived risk score (`raindrop_score`) that complements the deterministic rule-based scoring (`rule_score`). It is **advisory only** — it informs ranking but never overrides source-backed evidence or direct-hit findings.

## Current Implementation: Deterministic V1

**Model version:** `raindrop-v1-deterministic`

The V1 scorer is a rule-based feature scorer implemented in:
- `services/api/app/ml/raindrop_scorer.py` — `RaindropAmlScorer` adapter
- `services/api/app/ml/features.py` — Feature extraction from `InvestigationGraph`

### Feature Schema (v1)

| Family | Feature | Type | Description |
|--------|---------|------|-------------|
| Graph | `node_count` | int | Total nodes in the graph |
| Graph | `edge_count` | int | Total edges in the graph |
| Graph | `avg_degree` | float | Average node degree |
| Graph | `max_degree` | int | Maximum node degree |
| Graph | `density` | float | Graph density (edges / possible edges) |
| Node | `target_in_degree` | int | In-degree of the target (root) node |
| Node | `target_out_degree` | int | Out-degree of the target node |
| Node | `target_total_value_in` | float | Total ETH received by target |
| Node | `target_total_value_out` | float | Total ETH sent by target |
| Node | `target_tx_count` | int | Transaction count for target |
| Temporal | `time_span` | int | Seconds between first and last transaction |
| Temporal | `avg_time_between_txs` | float | Average gap between transactions |
| Temporal | `burst_score` | float | Coefficient of variation of gaps (0–1) |
| Value | `total_value` | float | Sum of all edge values |
| Value | `avg_value` | float | Mean edge value |
| Value | `max_value` | float | Maximum edge value |
| Value | `value_variance` | float | Population std dev of edge values |
| Risk | `risk_tag_count` | int | Nodes with risk tags (excluding trust_list) |
| Risk | `direct_hit_count` | int | Nodes with direct-hit categories (OFAC, etc.) |
| Other | `max_hop` | int | Maximum hop distance from target |

### Scoring Components (V1)

The V1 scorer combines five weighted components, each normalized to 0–100:

| Component | Weight | Signal |
|-----------|--------|--------|
| Centrality | 25% | High max_degree → higher score |
| Risk tags | 25% | Many risk tags / direct hits → higher score |
| Temporal | 20% | Bursty / rapid transactions → higher score |
| Value | 15% | Large value variance → higher score |
| Depth | 15% | Deep graph (many hops) → higher score |

**Final score** = `min(100, 0.25*centrality + 0.25*risk_tag + 0.20*temporal + 0.15*value + 0.15*depth)`

### Determinism Guarantee

The V1 scorer is fully deterministic: given the same `InvestigationGraph`, it always produces the same `RaindropResult`. No randomness, no external state.

---

## Future Trained Model Migration

### Architecture

The future model will replace the internals of `RaindropAmlScorer.predict()` while preserving the frozen interface:

```
predict(graph: InvestigationGraph) -> RaindropResult
```

The model will be based on the Harvard Raindrop architecture:
- **Input:** Irregular multivariate time series of risk channels
- **Architecture:** Temporal graph neural network (PyTorch/PyG)
- **Inference:** CPU-only (no GPU required for inference)
- **Training:** Optional GPU training on historical data

### Risk Channels (Future)

The trained model will process these channels as a Raindrop-shaped tensor:

1. **Value flow** — ETH/token transfer amounts over time
2. **Counterparty diversity** — Unique address interactions
3. **GoPlus behaviour** — Security flags from GoPlus API
4. **Watchlist hit** — Local/external watchlist matches
5. **Approval exposure** — Token approval patterns
6. **Hop exposure** — Distance from known-risky addresses
7. **Mixer/sanction proximity** — Distance from known mixers/sanctioned addresses
8. **Timing burst** — Transaction frequency patterns

### Migration Path

1. **Feature parity:** Ensure `extract_features()` captures all features needed by the trained model
2. **Model training:** Train on historical AML data with time-based or connected-component splits (avoid graph leakage)
3. **Validation:** Achieve target metrics on held-out test set
4. **Feature flag:** Gate the trained model behind `USE_TRAINED_RAINDROP=true` env var
5. **Shadow mode:** Run both deterministic and trained models; log disagreements
6. **Switchover:** Replace deterministic internals when metrics are validated

### Required Metrics

Before deploying a trained model, it must meet these thresholds on a held-out test set:

| Metric | Minimum | Target | Description |
|--------|---------|--------|-------------|
| **AUPRC** | 0.60 | 0.75 | Area Under Precision-Recall Curve |
| **AUROC** | 0.70 | 0.85 | Area Under ROC Curve |
| **Precision@K** | 0.50 | 0.70 | Precision at top-K predictions |
| **Recall@K** | 0.60 | 0.80 | Recall at top-K predictions |

Additionally:
- **Calibration plot:** Predicted probabilities should match observed frequencies
- **Latency:** p99 inference < 50ms on CPU (single graph)
- **Memory:** Model + features < 512MB RAM

### Data Split Strategy

To avoid graph leakage:
- **Time-based split:** Train on older data, test on newer data
- **Connected-component split:** Ensure no address appears in both train and test sets within the same connected component
- **Stratified sampling:** Maintain class balance across splits

---

## Model Versioning Strategy

### Version String Format

```
raindrop-v{schema_version}-{implementation_type}
```

Examples:
- `raindrop-v1-deterministic` — Current V1 rule-based scorer
- `raindrop-v2-ml` — Future trained model (schema v2)
- `raindrop-v2-ml-20260516` — Trained model with date stamp

### Artefact Versioning

Each model version is tracked with:

| Field | Description | Example |
|-------|-------------|---------|
| `model_version` | Unique identifier | `raindrop-v2-ml` |
| `feature_schema_version` | Schema version | `2` |
| `code_version` | Git commit hash | `abc123` |
| `data_version` | Training data hash | `def456` |
| `seed` | Random seed for reproducibility | `42` |
| `metrics` | Validation metrics JSON | See below |

### Model Card

A model card will be placed at `services/ml/raindrop_aml/MODEL_CARD.md` containing:

```markdown
# Raindrop AML Model Card

## Model Details
- **Model Version:** raindrop-v2-ml
- **Feature Schema Version:** 2
- **Code Version:** abc123
- **Data Version:** def456
- **Random Seed:** 42
- **Training Date:** 2026-05-16

## Intended Use
- Risk scoring for cryptocurrency transaction graphs
- Advisory only; never overrides source-backed evidence

## Training Data
- [Description of training data]
- [Time range]
- [Number of positive/negative examples]

## Evaluation Metrics
- AUPRC: 0.78
- AUROC: 0.87
- Precision@100: 0.72
- Recall@100: 0.83

## Limitations
- CPU inference only (no GPU required)
- Deterministic for same input
- May not generalize to unseen chain types

## Ethical Considerations
- Scores are advisory; human review required for dispositions
- No PII stored in model artefacts
```

---

## Integration with Scoring Pipeline

### Current Flow

```python
# In scoring.py
raindrop_result = self.raindrop.predict(graph)
raindrop_score = raindrop_result.score
raindrop_features = raindrop_result.features

# Final score: max of rule_score and weighted combination
final_score = min(100.0, max(rule_score, 0.65 * rule_score + 0.35 * raindrop_score))
```

### Advisory Guarantee

The `raindrop_score` is **advisory only**:
- It can increase `final_risk_score` when it detects patterns the rule engine misses
- It **never** overrides `rule_score` when rule_score is higher
- It **never** overrides direct-hit findings (OFAC, sanctions, etc.)
- The UI shows `rule_score`, `raindrop_score`, and `final_risk_score` separately

### Disposition Logic

```python
# Disposition is based on final_risk_score AND source_hits
# Direct hits ALWAYS force hold_for_manual_review regardless of score
if direct_hits:
    return "hold_for_manual_review"
if final_score >= 85:
    return "hold_for_manual_review"
if final_score >= 65:
    return "review"
# ...
```

---

## Testing

### Test Coverage

The ML layer tests (`services/api/app/tests/test_ml.py`) cover:

1. **Contract tests:** `predict()` returns `RaindropResult` with correct types
2. **Determinism tests:** Same graph → same result (100% reproducible)
3. **Range tests:** Score always in [0, 100]
4. **Feature tests:** Feature extraction correctness for all feature families
5. **Behaviour tests:** Score responds correctly to risk signals
6. **Explanation tests:** Explanations are human-readable and informative
7. **Integration tests:** ML layer integrates correctly with scoring pipeline

### Running Tests

```bash
PYTHONPATH=services/api pytest -q services/api/app/tests
```

---

## Questions / Contact

For questions about the Raindrop ML layer:
- **Owner:** `raindrop-ml-engineer`
- **Architecture approval:** `aml-architect`
- **Risk logic review:** `risk-logic-reviewer`

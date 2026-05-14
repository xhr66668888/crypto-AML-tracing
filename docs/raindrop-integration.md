# Raindrop AML Integration

## Source Model Summary

The original Raindrop research repository is the MIT-licensed Harvard/Zitnik Lab implementation of "Graph-Guided Network For Irregularly Sampled Multivariate Time Series." It was reviewed during planning and then removed from this business repository so the product codebase does not vendor a full research repo. The original model treats each sample as a graph of sensors, applies observation propagation between sensors, uses temporal positional encoding, and classifies irregular multivariate time series.

Important original source files reviewed during planning:

- `Raindrop/code/models_rd.py`: `Raindrop` and `Raindrop_v2` model definitions.
- `Raindrop/code/Ob_propagation.py`: graph message passing for observation propagation.
- `Raindrop/code/Raindrop.py`: training/evaluation script and split handling.
- `Raindrop/code/utils_rd.py`: normalization, masking, split, and evaluation helpers.

## AML Mapping

- Original sample: patient or activity segment.
- AML sample: one investigation target, address sequence, or path-level risk sample.
- Original sensor: clinical or activity sensor channel.
- AML channel: risk observation channel such as value flow, counterparty diversity, GoPlus behavior, watchlist hit, approval exposure, hop exposure, mixer/sanction proximity, and timing burst.
- Original irregular timestamps: medical observation times.
- AML timestamps: transaction block timestamps.
- Original graph: sensor dependency graph.
- AML Raindrop graph: risk-channel dependency graph, separate from the transaction graph.

## Implementation Rule

Do not import the old research scripts directly into the API. They are CUDA-heavy, pinned to older dependencies, and include research-only scripts. Port the architecture into `services/ml/raindrop_aml` behind the stable `RaindropAmlScorer.predict(graph)` interface.

## MVP Status

The current `RaindropAmlScorer` is a deterministic adapter that computes temporal irregularity, value dispersion, tagged-node exposure, and hop exposure. It gives the frontend and API a stable integration surface while the ML engineer ports and validates the real model.

## Acceptance Criteria For Real Model Port

- CPU inference works without CUDA.
- Training can run with optional GPU.
- Inputs and outputs are versioned.
- Metrics include AUPRC, AUROC, Precision@K, Recall@K, and calibration plots.
- Dataset split avoids graph leakage by using time-based or connected-component splits.
- Model artifacts include feature schema, random seed, code version, data version, and metric report.

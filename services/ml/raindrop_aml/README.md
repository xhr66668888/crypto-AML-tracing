# Raindrop AML Worker

This folder is reserved for the real Raindrop model port.

Current API integration lives in `services/api/app/ml/raindrop_aml.py` and exposes:

```python
score, features = RaindropAmlScorer().predict(graph)
```

The ML engineer should keep that interface stable while replacing the deterministic MVP logic with:

1. Feature extraction from investigation graphs into irregular multivariate time-series tensors.
2. A CPU-safe PyTorch implementation adapted from `Raindrop/code/models_rd.py`.
3. Training and evaluation scripts with versioned artifacts.
4. Exported inference artifact that the FastAPI process can load locally.

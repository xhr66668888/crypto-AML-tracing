"""Machine-learning scoring adapters.

Public surface
--------------
- ``RaindropAmlScorer``  – stable adapter imported by ``scoring.py``
- ``RaindropResult``     – immutable return type of ``predict()``
- ``extract_features``   – feature builder (used by scorer, importable for tests)
"""

from app.ml.features import extract_features
from app.ml.raindrop_scorer import RaindropAmlScorer, RaindropResult

__all__ = ["RaindropAmlScorer", "RaindropResult", "extract_features"]

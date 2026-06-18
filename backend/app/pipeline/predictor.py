"""
Loads artifacts/predictor.pkl (XGBoost via joblib) and exposes predict().
Falls back to the heuristic from the frontend mock when the file is absent
so the API works out-of-the-box before the real model is trained.
"""
import os
from typing import Any, Dict, Optional

import pandas as pd

_ARTIFACTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "artifacts")
)
_PREDICTOR_PATH = os.path.join(_ARTIFACTS_DIR, "predictor.pkl")

_model: Optional[Any] = None
_model_loaded: bool = False


def _load_model() -> Optional[Any]:
    global _model, _model_loaded
    if _model_loaded:
        return _model
    if os.path.exists(_PREDICTOR_PATH):
        import joblib
        _model = joblib.load(_PREDICTOR_PATH)
    _model_loaded = True
    return _model


def predict(features_dict: Dict[str, Any]) -> float:
    """Return predicted AUC in [0.5, 0.99]."""
    from .features import build_X

    model = _load_model()
    if model is not None:
        df = pd.DataFrame([features_dict])
        X = build_X(df)
        auc = float(model.predict(X)[0])
        return max(0.5, min(0.99, auc))

    # Heuristic fallback (mirrors frontend mock predictAuc)
    gap = max(0.0, features_dict.get("train_accuracy", 0) - features_dict.get("test_accuracy", 0))
    auc = 0.5 + gap * 0.9
    if features_dict.get("dropout", 0.1) < 0.1:
        auc += 0.04
    if features_dict.get("weight_decay", 1e-4) < 1e-4:
        auc += 0.03
    if not features_dict.get("data_augmentation", True):
        auc += 0.04
    if features_dict.get("epochs", 0) > 100:
        auc += 0.03
    if features_dict.get("nb_train_samples", 10_000) < 5_000:
        auc += 0.05
    if features_dict.get("embed_dim", 256) > 512:
        auc += 0.02
    if features_dict.get("dataset_modality") == "tabular":
        auc += 0.02
    return max(0.5, min(0.99, auc))

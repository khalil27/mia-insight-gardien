"""
Loads XGBoost meta-models (JSON format) and exposes predict().

Four models in backend/artifacts/:
  model_A_regressor.json   — 21 features (includes train/test accuracy + gap)   R²=0.98
  model_A_classifier.json  — same 21 features, predicts risk class              F1=0.95
  model_B_regressor.json   — 18 features (no train/test accuracy)               R²=0.98
  model_B_classifier.json  — same 18 features, predicts risk class              F1=0.945

Model A is selected when train_accuracy AND test_accuracy are present.
Model B is selected otherwise (hyperparameters only).

Risk classes: 0=Faible (<0.55), 1=Moyen (0.55-0.65), 2=Élevé (≥0.65)

Preprocessing applied inside this module before every inference:
  - model_type / dataset_modality  → integer via hardcoded LabelEncoder mapping
  - nb_params, nb_train_samples, nb_classes, params_per_sample → np.log1p
  - data_augmentation → int (0 or 1)
  - train_test_gap = max(0, train_accuracy - test_accuracy)  [Model A only]
"""

import os
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

_ARTIFACTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "artifacts")
)

# ── LabelEncoder mappings (alphabetical, same order as sklearn fit on training data) ──

MODEL_TYPE_ENC: Dict[str, int] = {
    "AlexNet": 0, "CNN": 1, "DenseNet": 2, "EfficientNet": 3, "MLP": 4,
    "RNN": 5, "ResNet": 6, "Transformer": 7, "VGG": 8, "ViT": 9,
    "ViT-B": 10, "ViT-Small": 11, "ViT-Tiny": 12, "WideResNet": 13,
}

MODALITY_ENC: Dict[str, int] = {"image": 0, "tabular": 1, "text": 2}

RISK_LABELS: Dict[int, str] = {0: "Faible", 1: "Moyen", 2: "Élevé"}

# ── Feature column lists (must match training order exactly) ──────────────────

FEATURES_A = [
    "model_type_enc", "nb_params_log", "depth", "embed_dim", "mlp_ratio",
    "patch_size", "dropout", "dataset_modality_enc", "nb_train_samples_log",
    "nb_classes_log", "data_augmentation", "epochs", "learning_rate",
    "batch_size", "weight_decay", "train_accuracy", "test_accuracy",
    "train_test_gap", "params_per_sample_log", "dataset_intra_variance",
    "dataset_inter_class_distance",
]

FEATURES_B = [
    "model_type_enc", "nb_params_log", "depth", "embed_dim", "mlp_ratio",
    "patch_size", "dropout", "dataset_modality_enc", "nb_train_samples_log",
    "nb_classes_log", "data_augmentation", "epochs", "learning_rate",
    "batch_size", "weight_decay", "params_per_sample_log",
    "dataset_intra_variance", "dataset_inter_class_distance",
]

# ── Lazy model registry ───────────────────────────────────────────────────────

_models: Dict[str, Any] = {}
_models_loaded: bool = False


def _load_models() -> None:
    global _models, _models_loaded
    if _models_loaded:
        return
    import xgboost as xgb
    for name, cls in (
        ("model_A_regressor",  xgb.XGBRegressor),
        ("model_A_classifier", xgb.XGBClassifier),
        ("model_B_regressor",  xgb.XGBRegressor),
        ("model_B_classifier", xgb.XGBClassifier),
    ):
        path = os.path.join(_ARTIFACTS_DIR, f"{name}.json")
        if os.path.exists(path):
            m = cls()
            m.load_model(path)
            _models[name] = m
    _models_loaded = True


# ── Preprocessing ─────────────────────────────────────────────────────────────

def _preprocess(raw: Dict[str, Any]) -> Dict[str, Any]:
    f = dict(raw)

    # LabelEncoder
    f["model_type_enc"] = MODEL_TYPE_ENC.get(str(f.get("model_type", "CNN")), 1)
    f["dataset_modality_enc"] = MODALITY_ENC.get(str(f.get("dataset_modality", "tabular")), 1)

    # Log transforms
    nb_params        = max(0, int(f.get("nb_params", 100_000)))
    nb_train_samples = max(0, int(f.get("nb_train_samples", 10_000)))
    nb_classes       = max(0, int(f.get("nb_classes", 2)))
    params_per_sample = nb_params / max(1, nb_train_samples)

    f["nb_params_log"]        = np.log1p(nb_params)
    f["nb_train_samples_log"] = np.log1p(nb_train_samples)
    f["nb_classes_log"]       = np.log1p(nb_classes)
    f["params_per_sample_log"] = np.log1p(params_per_sample)

    # data_augmentation as int
    f["data_augmentation"] = int(bool(f.get("data_augmentation", False)))

    # train_test_gap (Model A only, but compute anyway for completeness)
    train_acc = f.get("train_accuracy")
    test_acc  = f.get("test_accuracy")
    if train_acc is not None and test_acc is not None:
        f["train_test_gap"] = max(0.0, float(train_acc) - float(test_acc))

    return f


def _has_training_outcomes(raw: Dict[str, Any]) -> bool:
    return raw.get("train_accuracy") is not None and raw.get("test_accuracy") is not None


# ── Public API ────────────────────────────────────────────────────────────────

def predict(features_dict: Dict[str, Any]) -> Tuple[float, str, str]:
    """Return (predicted_auc, risk_level, model_used).

    model_used is "A", "B", or "heuristique".
    Selects Model A when train_accuracy + test_accuracy are present (best accuracy).
    Falls back to Model B (hyperparameters only) or to the heuristic if no model file exists.
    """
    _load_models()

    use_A = _has_training_outcomes(features_dict) and "model_A_regressor" in _models
    use_B = not use_A and "model_B_regressor" in _models

    if use_A or use_B:
        prefix    = "model_A" if use_A else "model_B"
        feat_cols = FEATURES_A if use_A else FEATURES_B
        variant   = "A" if use_A else "B"

        f  = _preprocess(features_dict)
        df = pd.DataFrame([{col: f.get(col, np.nan) for col in feat_cols}])

        reg = _models.get(f"{prefix}_regressor")
        clf = _models.get(f"{prefix}_classifier")

        auc = float(reg.predict(df)[0]) if reg is not None else _fallback_auc(features_dict)
        auc = round(max(0.5, min(0.99, auc)), 3)

        if clf is not None:
            risk_class = int(clf.predict(df)[0])
            risk_level = RISK_LABELS.get(risk_class, "Moyen")
        else:
            from .features import auc_to_risk
            risk_level = auc_to_risk(auc)

        return auc, risk_level, variant

    # ── Full heuristic fallback (no model files present) ─────────────────────
    auc = round(_fallback_auc(features_dict), 3)
    from .features import auc_to_risk
    return auc, auc_to_risk(auc), "heuristique"


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _fallback_auc(features_dict: Dict[str, Any]) -> float:
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

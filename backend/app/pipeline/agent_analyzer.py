"""
Agent Coordinator — orchestre agent_model et agent_dataset.
Conservé pour la compatibilité avec l'endpoint legacy /evaluate.
"""
from typing import Any, Dict, Optional

from . import agent_model, agent_dataset

_DEFAULTS: Dict[str, Any] = {
    "model_type":                  "CNN",
    "dataset_modality":            "tabular",
    "depth":                       6,
    "num_heads":                   0,
    "embed_dim":                   0,
    "mlp_ratio":                   0.0,
    "nb_params":                   100_000,
    "patch_size":                  0,
    "epochs":                      50,
    "learning_rate":               0.001,
    "batch_size":                  64,
    "dropout":                     0.0,
    "weight_decay":                0.0,
    "data_augmentation":           False,
    "nb_train_samples":            10_000,
    "nb_classes":                  2,
    "dataset_intra_variance":      0.5,
    "dataset_inter_class_distance": 0.5,
    "train_accuracy":              0.9,
    "test_accuracy":               0.85,
}


def analyze(
    model_bytes:      Optional[bytes],
    model_filename:   str,
    config_bytes:     Optional[bytes],
    dataset_bytes:    Optional[bytes],
    dataset_filename: str,
    dataset_url:      Optional[str],
    manual_params:    Dict[str, Any],
) -> Dict[str, Any]:
    """Return a complete EvaluateInput-compatible dict (manual params win)."""
    features: Dict[str, Any] = {}

    if model_bytes:
        try:
            features.update(agent_model.analyze_pkl(model_bytes, model_filename))
        except Exception:
            pass

    if config_bytes:
        try:
            features.update(agent_model.analyze_config(config_bytes))
        except Exception:
            pass

    if dataset_bytes or dataset_url:
        try:
            features.update(agent_dataset.analyze(dataset_bytes, dataset_filename, dataset_url))
        except Exception:
            pass

    for k, v in manual_params.items():
        if v is not None and v != "":
            features[k] = v

    for k, v in _DEFAULTS.items():
        features.setdefault(k, v)

    _coerce(features)
    return features


def summary_message(features: Dict[str, Any]) -> str:
    return (
        f"Modèle : {features.get('model_type', '?')} · "
        f"{features.get('nb_params', 0):,} params · "
        f"Dataset : {features.get('nb_train_samples', 0):,} samples · "
        f"{features.get('nb_classes', '?')} classes"
    )


def _coerce(f: Dict[str, Any]) -> None:
    int_keys   = ("depth", "num_heads", "embed_dim", "nb_params", "patch_size",
                  "epochs", "batch_size", "nb_train_samples", "nb_classes")
    float_keys = ("mlp_ratio", "learning_rate", "dropout", "weight_decay",
                  "dataset_intra_variance", "dataset_inter_class_distance",
                  "train_accuracy", "test_accuracy")
    for k in int_keys:
        try:
            f[k] = int(f[k])
        except Exception:
            pass
    for k in float_keys:
        try:
            f[k] = float(f[k])
        except Exception:
            pass
    if isinstance(f.get("data_augmentation"), str):
        f["data_augmentation"] = f["data_augmentation"].lower() in ("true", "1", "yes")

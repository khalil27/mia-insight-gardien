"""
Feature schema, build_X, and auc_to_risk.

MIA risk thresholds:
  AUC < 0.55  → Faible
  0.55 ≤ AUC < 0.65 → Moyen
  AUC ≥ 0.65  → Élevé
"""
from typing import Any, Dict

import numpy as np
import pandas as pd

MODEL_TYPES = [
    "CNN", "MLP", "ResNet", "WideResNet", "DenseNet",
    "AlexNet", "ViT", "ViT-B", "EfficientNet", "MobileNet", "Transformer",
]
MODALITIES = ["image", "tabular", "text"]

FEATURE_COLUMNS = [
    "depth",
    "num_heads",
    "embed_dim",
    "mlp_ratio",
    "nb_params",
    "patch_size",
    "epochs",
    "learning_rate",
    "batch_size",
    "dropout",
    "weight_decay",
    "data_augmentation",
    "nb_train_samples",
    "nb_classes",
    "dataset_intra_variance",
    "dataset_inter_class_distance",
    "train_accuracy",
    "test_accuracy",
    "params_per_sample",
    "train_test_gap",
    # model_type one-hot (11 types)
    "model_type_CNN",
    "model_type_MLP",
    "model_type_ResNet",
    "model_type_WideResNet",
    "model_type_DenseNet",
    "model_type_AlexNet",
    "model_type_ViT",
    "model_type_ViT-B",
    "model_type_EfficientNet",
    "model_type_MobileNet",
    "model_type_Transformer",
    # dataset_modality one-hot
    "dataset_modality_image",
    "dataset_modality_tabular",
    "dataset_modality_text",
]


def build_X(df: pd.DataFrame) -> pd.DataFrame:
    """Transform a raw-input DataFrame into the feature matrix expected by the predictor."""
    result = df.copy()

    result["train_test_gap"]    = (result["train_accuracy"] - result["test_accuracy"]).clip(lower=0)
    result["params_per_sample"] = result["nb_params"] / result["nb_train_samples"].clip(lower=1)

    for mt in MODEL_TYPES:
        result[f"model_type_{mt}"] = (result["model_type"] == mt).astype(int)

    for mod in MODALITIES:
        result[f"dataset_modality_{mod}"] = (result["dataset_modality"] == mod).astype(int)

    result = result.drop(columns=["model_type", "dataset_modality"], errors="ignore")

    for col in FEATURE_COLUMNS:
        if col not in result.columns:
            result[col] = np.nan

    return result[FEATURE_COLUMNS]


def auc_to_risk(auc: float) -> str:
    if auc < 0.55:
        return "Faible"
    if auc < 0.65:
        return "Moyen"
    return "Élevé"

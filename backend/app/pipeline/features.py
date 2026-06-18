"""
Feature schema and auc_to_risk.

FEATURE_COLUMNS lists the 21 features of Model A (the primary model).
Used by the insights endpoint to label feature importances.

MIA risk thresholds:
  AUC < 0.55        → Faible
  0.55 ≤ AUC < 0.65 → Moyen
  AUC ≥ 0.65        → Élevé
"""

# 21 features of Model A (with training outcomes) — matches FEATURES_A in predictor.py
FEATURE_COLUMNS = [
    "model_type_enc",
    "nb_params_log",
    "depth",
    "embed_dim",
    "mlp_ratio",
    "patch_size",
    "dropout",
    "dataset_modality_enc",
    "nb_train_samples_log",
    "nb_classes_log",
    "data_augmentation",
    "epochs",
    "learning_rate",
    "batch_size",
    "weight_decay",
    "train_accuracy",
    "test_accuracy",
    "train_test_gap",
    "params_per_sample_log",
    "dataset_intra_variance",
    "dataset_inter_class_distance",
]


def auc_to_risk(auc: float) -> str:
    if auc < 0.55:
        return "Faible"
    if auc < 0.65:
        return "Moyen"
    return "Élevé"

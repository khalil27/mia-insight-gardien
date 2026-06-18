"""
Generates recommendations and a free-text report from an evaluation result.

Rule-based for now; the generate_report function has an LLM extension point
marked with # LLM_HOOK so a later version can swap in an API call.
"""
from typing import Any, Dict, List


def generate_recommendations(input_dict: Dict[str, Any], auc: float, risk_level: str) -> List[str]:
    gap = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))
    recs: List[str] = []

    if gap > 0.1:
        recs.append("Réduire le sur-apprentissage : ↑ régularisation, ↓ epochs ou early stopping.")
    if input_dict.get("dropout", 0.1) < 0.1:
        recs.append("Augmenter le dropout (0.1 – 0.3) pour limiter la mémorisation.")
    if input_dict.get("weight_decay", 1e-4) < 1e-4:
        recs.append("Augmenter le weight decay (≥ 1e-4).")
    if not input_dict.get("data_augmentation", True):
        recs.append("Activer la data augmentation pour brouiller les signatures par exemple.")
    if input_dict.get("nb_train_samples", 10_000) < 5_000:
        recs.append("Élargir le dataset d'entraînement (effet significatif sur la MIA).")
    if auc >= 0.65:
        recs.append("Envisager une défense : DP-SGD, knowledge distillation ou MemGuard.")

    if not recs:
        recs.append("Configuration robuste : maintenir la régularisation et surveiller le gap.")

    return recs


def generate_report(input_dict: Dict[str, Any], auc: float, risk_level: str) -> str:
    gap = max(0.0, input_dict.get("train_accuracy", 0) - input_dict.get("test_accuracy", 0))

    # LLM_HOOK: replace the return below with an LLM API call for richer reports.
    return (
        f"Estimation AUC ≈ {auc:.3f} sur la base d'un méta-modèle entraîné sur "
        f"des centaines de runs Transformer. "
        f"Gap train/test = {gap:.3f}. Niveau : {risk_level}."
    )

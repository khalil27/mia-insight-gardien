"""
Construit une requête sémantique depuis les features d'évaluation
et retourne les chunks les plus pertinents depuis la base RAG.
"""
from typing import Any, Dict, List

from . import store


def _build_query(features: Dict[str, Any], auc: float, risk_level: str) -> str:
    """Construit une query en langage naturel à partir du contexte d'évaluation."""
    parts = ["membership inference attack privacy"]

    model_type = features.get("model_type", "")
    modality   = features.get("dataset_modality", "")
    if model_type:
        parts.append(f"{model_type} model")
    if modality:
        parts.append(f"{modality} data")

    parts.append(f"AUC {auc:.2f} {risk_level} risk")

    train_acc = features.get("train_accuracy")
    test_acc  = features.get("test_accuracy")
    if train_acc is not None and test_acc is not None:
        gap = max(0.0, float(train_acc) - float(test_acc))
        if gap > 0.1:
            parts.append(f"overfitting train test gap {gap:.2f}")

    dropout      = features.get("dropout", 0.1)
    weight_decay = features.get("weight_decay", 1e-4)
    if float(dropout) < 0.1:
        parts.append("low dropout memorization")
    if float(weight_decay) < 1e-4:
        parts.append("no regularization generalization")

    if auc >= 0.65:
        parts.append("high vulnerability defense differential privacy distillation")
    elif auc >= 0.55:
        parts.append("moderate vulnerability regularization mitigation")

    nb_samples = features.get("nb_train_samples", 10_000)
    if int(nb_samples) < 5_000:
        parts.append("small dataset memorization risk")

    return " ".join(parts)


def retrieve(features: Dict[str, Any], auc: float, risk_level: str, n: int = 4) -> List[str]:
    """Retourne les n chunks les plus pertinents pour enrichir le rapport.
    Retourne [] si la base RAG n'est pas disponible (dégradation silencieuse).
    """
    if not store.is_available():
        return []

    query   = _build_query(features, auc, risk_level)
    results = store.search(query, n_results=n)
    return [r["text"] for r in results]

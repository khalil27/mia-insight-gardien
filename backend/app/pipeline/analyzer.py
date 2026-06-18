"""
Computes derived features from raw EvaluateInput before feeding the predictor.
Runs independently of any trained model so it can evolve without retraining.
"""
from typing import Any, Dict


def analyze(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Return input_dict enriched with derived features."""
    nb_params = max(1, input_dict.get("nb_params", 1))
    nb_train_samples = max(1, input_dict.get("nb_train_samples", 1))
    train_acc = input_dict.get("train_accuracy", 0.0)
    test_acc = input_dict.get("test_accuracy", 0.0)

    return {
        **input_dict,
        "params_per_sample": nb_params / nb_train_samples,
        "train_test_gap": max(0.0, train_acc - test_acc),
    }

"""
Agent Modèle — extrait les features depuis un fichier .pkl et optionnellement config.json.
"""
import io
import json
from typing import Any, Dict, List, Optional, Tuple


_TYPE_HINTS: List[Tuple[str, str]] = [
    ("vit-b",          "ViT-B"),
    ("vit_b",          "ViT-B"),
    ("vitb",           "ViT-B"),
    ("vit",            "ViT"),
    ("vision_transformer", "ViT"),
    ("wideresnet",     "WideResNet"),
    ("wide_resnet",    "WideResNet"),
    ("resnet",         "ResNet"),
    ("densenet",       "DenseNet"),
    ("alexnet",        "AlexNet"),
    ("efficientnet",   "EfficientNet"),
    ("mobilenet",      "MobileNet"),
    ("transformer",    "Transformer"),
    ("bert",           "Transformer"),
    ("gpt",            "Transformer"),
    ("t5",             "Transformer"),
    ("llama",          "Transformer"),
    ("mlpclassifier",  "MLP"),
    ("mlp",            "MLP"),
    ("multilayer",     "MLP"),
    ("cnn",            "CNN"),
    ("conv",           "CNN"),
    ("sequential",     "CNN"),
]


def _detect_model_type(cls_name: str, filename: str) -> Optional[str]:
    ref = (cls_name + " " + filename).lower()
    for key, value in _TYPE_HINTS:
        if key in ref:
            return value
    return None


def _extract_xgb(model: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    try:
        import xgboost as xgb
        if not isinstance(model, xgb.XGBModel):
            return result
        p = model.get_params()
        result["learning_rate"] = float(p.get("learning_rate", 0.1))
        result["depth"]         = int(p.get("max_depth", 6))
        result["epochs"]        = int(p.get("n_estimators", 100))
        result["weight_decay"]  = float(p.get("reg_lambda", 1.0))
        result["num_heads"]  = 0
        result["embed_dim"]  = 0
        result["mlp_ratio"]  = 0.0
        result["patch_size"] = 0
        result["dropout"]    = 0.0
        dump   = model.get_booster().get_dump()
        leaves = sum(line.count("leaf") for tree in dump for line in tree.split("\n"))
        result["nb_params"]  = max(leaves, 1)
    except Exception:
        pass
    return result


def _extract_sklearn(model: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    try:
        if hasattr(model, "n_estimators"):
            result["epochs"] = int(model.n_estimators)
        if hasattr(model, "max_depth") and model.max_depth:
            result["depth"] = int(model.max_depth)
        if hasattr(model, "learning_rate"):
            result["learning_rate"] = float(model.learning_rate)
        if hasattr(model, "estimators_"):
            result["nb_params"] = sum(
                getattr(getattr(e, "tree_", None), "node_count", 0)
                for e in model.estimators_
            )
        elif hasattr(model, "coef_"):
            result["nb_params"] = int(model.coef_.size)
    except Exception:
        pass
    return result


def analyze_pkl(model_bytes: bytes, filename: str) -> Dict[str, Any]:
    import joblib
    model = joblib.load(io.BytesIO(model_bytes))
    result: Dict[str, Any] = {}

    cls_name = type(model).__name__
    detected = _detect_model_type(cls_name, filename)
    if detected:
        result["model_type"] = detected

    xgb_params = _extract_xgb(model)
    if xgb_params:
        if "model_type" not in result:
            result["model_type"] = "CNN"
        result.update(xgb_params)
    else:
        result.update(_extract_sklearn(model))

    return result


def analyze_config(config_bytes: bytes) -> Dict[str, Any]:
    """Extract Transformer architecture params from a HuggingFace config.json."""
    cfg = json.loads(config_bytes.decode())
    result: Dict[str, Any] = {}

    for k in ("num_hidden_layers", "num_layers", "n_layers", "depth"):
        if k in cfg:
            result["depth"] = int(cfg[k])
            break
    for k in ("num_attention_heads", "num_heads", "n_heads"):
        if k in cfg:
            result["num_heads"] = int(cfg[k])
            break
    for k in ("hidden_size", "d_model", "embed_dim"):
        if k in cfg:
            result["embed_dim"] = int(cfg[k])
            break
    if "intermediate_size" in cfg and cfg.get("hidden_size", 0) > 0:
        result["mlp_ratio"] = round(cfg["intermediate_size"] / cfg["hidden_size"], 2)
    for k in ("hidden_dropout_prob", "attention_probs_dropout_prob", "dropout"):
        if k in cfg:
            result["dropout"] = float(cfg[k])
            break
    if "patch_size" in cfg:
        result["patch_size"] = int(cfg["patch_size"])

    arch = cfg.get("model_type", "").lower()
    if "vit" in arch:
        result["model_type"] = "ViT"
        result["dataset_modality"] = "image"
    elif any(k in arch for k in ("bert", "roberta", "gpt", "llama", "t5", "xlm")):
        result["model_type"] = "Transformer"
        result["dataset_modality"] = "text"

    return result


def summary_message(features: Dict[str, Any]) -> str:
    parts = [f"Modèle : {features.get('model_type', '?')}"]
    if features.get("nb_params"):
        parts.append(f"{features['nb_params']:,} params")
    if features.get("depth"):
        parts.append(f"profondeur : {features['depth']}")
    if features.get("learning_rate"):
        parts.append(f"lr : {features['learning_rate']}")
    return " · ".join(parts)

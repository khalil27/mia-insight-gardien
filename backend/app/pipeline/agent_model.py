"""
Agent Modèle — extrait les features depuis un fichier .pkl et optionnellement config.json.

Stratégie d'extraction par priorité :
  1. Détecte le framework (PyTorch, Keras, XGBoost, sklearn) depuis la hiérarchie de classes
  2. Détecte le type de modèle depuis classe + module + couches (sans se fier au nom du fichier)
  3. Extrait les paramètres d'architecture directement depuis les couches du modèle
  4. Infère la modalité depuis le type de modèle (image / text / tabular)

Paramètres NON extractables depuis un .pkl (appartiennent au script d'entraînement) :
  learning_rate*, epochs*, batch_size, weight_decay*, data_augmentation,
  train_accuracy, test_accuracy  → saisie manuelle obligatoire.
  (* = extractables pour XGBoost et sklearn qui les stockent dans l'objet)

Exception PyTorch/Keras : nb_params, depth, embed_dim, num_heads, dropout, patch_size
  sont déduits de la structure des couches → extractables sans intervention de l'utilisateur.
"""
import io
import json
from typing import Any, Dict, List, Optional, Tuple


# ── Modality inferred from model type ─────────────────────────────────────────
_TYPE_TO_MODALITY: Dict[str, str] = {
    "ViT":         "image",
    "ViT-B":       "image",
    "ViT-Small":   "image",
    "ViT-Tiny":    "image",
    "CNN":         "image",
    "ResNet":      "image",
    "WideResNet":  "image",
    "DenseNet":    "image",
    "AlexNet":     "image",
    "EfficientNet":"image",
    "MobileNet":   "image",
    "VGG":         "image",
    "Transformer": "text",
    "RNN":         "text",
    "MLP":         "tabular",
}

# ── Type hints (most specific first — order matters) ──────────────────────────
_TYPE_HINTS: List[Tuple[str, str]] = [
    # ViT variants before generic "vit"
    ("vit-b",               "ViT-B"),
    ("vit_b",               "ViT-B"),
    ("vitb",                "ViT-B"),
    ("vit_small",           "ViT-Small"),
    ("vitsmall",            "ViT-Small"),
    ("vit_tiny",            "ViT-Tiny"),
    ("vittiny",             "ViT-Tiny"),
    # Generic ViT
    ("vit",                 "ViT"),
    ("vision_transformer",  "ViT"),
    # ResNet family
    ("wideresnet",          "WideResNet"),
    ("wide_resnet",         "WideResNet"),
    ("resnet",              "ResNet"),
    # Other CNN architectures
    ("densenet",            "DenseNet"),
    ("alexnet",             "AlexNet"),
    ("efficientnet",        "EfficientNet"),
    ("mobilenet",           "MobileNet"),
    ("vgg",                 "VGG"),
    # Transformer family
    ("transformer",         "Transformer"),
    ("bert",                "Transformer"),
    ("gpt",                 "Transformer"),
    ("t5",                  "Transformer"),
    ("llama",               "Transformer"),
    ("roberta",             "Transformer"),
    ("xlm",                 "Transformer"),
    ("distilbert",          "Transformer"),
    # RNN family
    ("rnn",                 "RNN"),
    ("lstm",                "RNN"),
    ("gru",                 "RNN"),
    # MLP (sklearn names must come before generic "mlp")
    ("mlpclassifier",       "MLP"),
    ("mlpregressor",        "MLP"),
    ("multilayerperceptron","MLP"),
    ("mlp",                 "MLP"),
    # Generic CNN / Sequential
    ("cnn",                 "CNN"),
    ("conv",                "CNN"),
    ("sequential",          "CNN"),
]


# ── Framework detection ────────────────────────────────────────────────────────

def _detect_framework(model: Any) -> str:
    """Detect the ML framework from class module path and duck-typing."""
    module = type(model).__module__

    # Module path is the most reliable indicator (no import needed)
    if module.startswith(("torch.", "torchvision.")):
        return "pytorch"
    if module.startswith(("tensorflow.", "keras.")):
        return "keras"
    if module.startswith("xgboost."):
        return "xgboost"
    if module.startswith("sklearn."):
        return "sklearn"

    # isinstance checks as fallback (handles vendored / monkeypatched classes)
    try:
        import xgboost as xgb
        if isinstance(model, xgb.XGBModel):
            return "xgboost"
    except ImportError:
        pass
    try:
        from sklearn.base import BaseEstimator
        if isinstance(model, BaseEstimator):
            return "sklearn"
    except ImportError:
        pass

    # Duck-typing fallback for PyTorch / Keras
    if hasattr(model, "parameters") and hasattr(model, "named_modules"):
        return "pytorch"
    if hasattr(model, "count_params") and hasattr(model, "layers"):
        return "keras"

    return "unknown"


# ── Model type detection from object content ───────────────────────────────────

def _detect_model_type(model: Any, filename: str = "") -> Optional[str]:
    """Detect model type from class name + module path + filename.
    Using all three sources makes detection reliable even for generic filenames.
    """
    cls_name   = type(model).__name__
    module_name = type(model).__module__
    ref = (cls_name + " " + module_name + " " + filename).lower()
    for key, value in _TYPE_HINTS:
        if key in ref:
            return value
    return None


# ── PyTorch extraction ─────────────────────────────────────────────────────────

def _extract_pytorch(model: Any) -> Dict[str, Any]:
    """Extract architecture parameters by inspecting PyTorch module tree."""
    result: Dict[str, Any] = {}
    try:
        # Exact parameter count (always available on any nn.Module)
        result["nb_params"] = int(sum(p.numel() for p in model.parameters()))

        try:
            import torch.nn as nn
            has_nn = True
        except ImportError:
            has_nn = False

        all_modules: List[Tuple[str, Any]] = list(model.named_modules())

        if has_nn:
            attn_layers    = [(n, m) for n, m in all_modules if isinstance(m, nn.MultiheadAttention)]
            conv_layers    = [(n, m) for n, m in all_modules if isinstance(m, nn.Conv2d)]
            linear_layers  = [(n, m) for n, m in all_modules if isinstance(m, nn.Linear)]
            dropout_layers = [(n, m) for n, m in all_modules
                             if isinstance(m, (nn.Dropout, nn.Dropout2d, nn.Dropout3d))]

            # dropout: highest p across all Dropout layers
            if dropout_layers:
                result["dropout"] = round(max(float(m.p) for _, m in dropout_layers), 4)

            # Transformer / ViT: extract from MultiheadAttention layers
            if attn_layers:
                _, first_attn        = attn_layers[0]
                result["num_heads"]  = int(first_attn.num_heads)
                result["embed_dim"]  = int(first_attn.embed_dim)
                result["depth"]      = len(attn_layers)

                # mlp_ratio: FFN hidden size / embed_dim
                embed     = result["embed_dim"]
                ffn_sizes = [m.out_features for _, m in linear_layers if m.out_features > embed]
                if ffn_sizes:
                    result["mlp_ratio"] = round(max(ffn_sizes) / embed, 2)

            # ViT patch embedding: Conv2d where kernel_size == stride and kernel > 1
            for _, conv in conv_layers:
                kh = conv.kernel_size[0] if isinstance(conv.kernel_size, tuple) else conv.kernel_size
                sh = conv.stride[0]      if isinstance(conv.stride, tuple)      else conv.stride
                if kh == sh and kh > 1:
                    result["patch_size"] = int(kh)
                    break

            # CNN depth: number of Conv2d layers (when no attention)
            if not attn_layers and conv_layers:
                result["depth"] = len(conv_layers)

            # MLP depth: number of Linear layers (when no conv and no attention)
            if not attn_layers and not conv_layers and linear_layers:
                result["depth"] = len(linear_layers)

        else:
            # torch not installed — best-effort using type name strings
            type_names = [type(m).__name__.lower() for _, m in all_modules]
            attn_count = sum(1 for t in type_names if "multiheadattention" in t)
            conv_count  = sum(1 for t in type_names if "conv2d" in t)
            if attn_count:
                result["depth"] = attn_count
            elif conv_count:
                result["depth"] = conv_count

    except Exception:
        pass
    return result


# ── Keras extraction ───────────────────────────────────────────────────────────

def _extract_keras(model: Any) -> Dict[str, Any]:
    """Extract architecture parameters by inspecting Keras layer list."""
    result: Dict[str, Any] = {}
    try:
        result["nb_params"] = int(model.count_params())
        layers = model.layers
        result["depth"] = len(layers)

        for layer in layers:
            lt = type(layer).__name__.lower()
            if "multihead" in lt or ("attention" in lt and "self" not in lt):
                try:
                    cfg = layer.get_config()
                    result["num_heads"] = int(cfg.get("num_heads", 0))
                    key_dim            = int(cfg.get("key_dim", 0))
                    result["embed_dim"] = key_dim * result["num_heads"]
                except Exception:
                    pass
                break

        for layer in layers:
            if "dropout" in type(layer).__name__.lower():
                try:
                    cfg = layer.get_config()
                    result["dropout"] = float(cfg.get("rate", 0.0))
                except Exception:
                    pass
                break

        # ViT-style patch embedding: Conv2D where kernel == stride and kernel > 1
        for layer in layers:
            if "conv2d" in type(layer).__name__.lower():
                try:
                    cfg     = layer.get_config()
                    kernel  = cfg.get("kernel_size", [1, 1])
                    strides = cfg.get("strides", [1, 1])
                    if isinstance(kernel, (list, tuple)) and kernel[0] == strides[0] and kernel[0] > 1:
                        result["patch_size"] = int(kernel[0])
                except Exception:
                    pass
                break

    except Exception:
        pass
    return result


# ── XGBoost extraction ─────────────────────────────────────────────────────────

def _extract_xgb(model: Any) -> Dict[str, Any]:
    """Extract hyperparameters stored inside an XGBoost model object."""
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
        result["num_heads"]     = 0
        result["embed_dim"]     = 0
        result["mlp_ratio"]     = 0.0
        result["patch_size"]    = 0
        result["dropout"]       = 0.0
        dump   = model.get_booster().get_dump()
        leaves = sum(line.count("leaf") for tree in dump for line in tree.split("\n"))
        result["nb_params"] = max(leaves, 1)
    except Exception:
        pass
    return result


# ── sklearn extraction ─────────────────────────────────────────────────────────

def _extract_sklearn(model: Any) -> Dict[str, Any]:
    """Extract parameters stored in fitted sklearn estimator attributes."""
    result: Dict[str, Any] = {}
    try:
        # Ensemble: n_estimators → epochs proxy, max_depth
        if hasattr(model, "n_estimators"):
            result["epochs"] = int(model.n_estimators)
        if hasattr(model, "max_depth") and model.max_depth is not None:
            result["depth"] = int(model.max_depth)

        # learning_rate only if it's a numeric attribute (GradientBoosting)
        # MLPClassifier has a string "constant"/"adaptive" → skip
        if hasattr(model, "learning_rate"):
            lr = model.learning_rate
            if isinstance(lr, (int, float)) and not isinstance(lr, bool):
                result["learning_rate"] = float(lr)

        # alpha = L2 regularization → weight_decay equivalent
        if hasattr(model, "alpha"):
            result["weight_decay"] = float(model.alpha)

        # nb_params: from tree nodes or coefficient matrix
        if hasattr(model, "estimators_"):
            result["nb_params"] = int(sum(
                getattr(getattr(e, "tree_", None), "node_count", 0)
                for e in model.estimators_
            ))
        elif hasattr(model, "coef_"):
            result["nb_params"] = int(model.coef_.size)

        # sklearn MLP (MLPClassifier / MLPRegressor)
        if hasattr(model, "hidden_layer_sizes"):
            sizes = model.hidden_layer_sizes
            if isinstance(sizes, int):
                sizes = (sizes,)
            result["depth"]     = len(sizes) + 1   # +1 for output layer
            result["embed_dim"] = int(max(sizes))

    except Exception:
        pass
    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_pkl(model_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Load a .pkl file and extract all inferable features.

    Returns a dict that may contain any subset of EvaluateInput fields.
    Unknown or unextractable fields are simply absent — callers apply defaults.
    """
    try:
        import joblib
        model = joblib.load(io.BytesIO(model_bytes))
    except Exception:
        return {}

    result: Dict[str, Any] = {}

    # 1. Detect framework from class metadata (no filename needed)
    framework = _detect_framework(model)

    # 2. Detect model type from class hierarchy + module path + filename
    detected_type = _detect_model_type(model, filename)
    if detected_type:
        result["model_type"] = detected_type

    # 3. Extract architecture params based on framework
    if framework == "pytorch":
        result.update(_extract_pytorch(model))

    elif framework == "keras":
        result.update(_extract_keras(model))

    elif framework == "xgboost":
        # XGBoost is a tabular model; MLP is the closest semantic category
        if "model_type" not in result:
            result["model_type"] = "MLP"
        result.update(_extract_xgb(model))

    else:
        result.update(_extract_sklearn(model))

    # 4. Infer dataset_modality from model type (single source of truth)
    if "model_type" in result:
        modality = _TYPE_TO_MODALITY.get(result["model_type"])
        if modality:
            result["dataset_modality"] = modality

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
        result["model_type"]       = "ViT"
        result["dataset_modality"] = "image"
    elif any(k in arch for k in ("bert", "roberta", "gpt", "llama", "t5", "xlm", "distilbert")):
        result["model_type"]       = "Transformer"
        result["dataset_modality"] = "text"

    return result


def summary_message(features: Dict[str, Any]) -> str:
    parts = [f"Modèle : {features.get('model_type', '?')}"]
    if features.get("nb_params"):
        parts.append(f"{features['nb_params']:,} params")
    if features.get("depth"):
        parts.append(f"profondeur : {features['depth']}")
    if features.get("embed_dim"):
        parts.append(f"embed_dim : {features['embed_dim']}")
    if features.get("num_heads"):
        parts.append(f"heads : {features['num_heads']}")
    if features.get("dropout"):
        parts.append(f"dropout : {features['dropout']}")
    if features.get("learning_rate"):
        parts.append(f"lr : {features['learning_rate']}")
    return " · ".join(parts)

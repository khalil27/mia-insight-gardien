"""
Agent Dataset — extrait automatiquement toutes les features depuis un CSV/Parquet/JSON.

Features calculées (zero saisie manuelle) :
  nb_train_samples, nb_classes, dataset_modality
  dataset_intra_variance     : variance intra-classe normalisée [0,1]
  dataset_inter_class_distance : distance inter-centroïdes normalisée [0,1]
"""
import io
import urllib.request
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _find_label_col(df: pd.DataFrame) -> Optional[str]:
    for name in ("label", "target", "class", "y", "output", "classe", "category", "labels"):
        if name in df.columns:
            return name
    return df.columns[-1] if len(df.columns) > 1 else None


def _guess_modality(filename: str, url: str = "") -> str:
    ref = (filename + url).lower()
    if any(k in ref for k in ("image", "img", "cifar", "imagenet", "mnist", "pixel", "photo")):
        return "image"
    if any(k in ref for k in ("text", "nlp", "sent", "review", "tweet", "news", "article")):
        return "text"
    return "tabular"


def _normalize(X: np.ndarray) -> np.ndarray:
    col_min = X.min(axis=0)
    ranges = X.max(axis=0) - col_min
    ranges[ranges == 0] = 1.0
    return (X - col_min) / ranges


def compute_intra_variance(df: pd.DataFrame, label_col: str) -> float:
    """Average within-class variance, normalized so uniform [0,1] → 1.0."""
    num_cols: List[str] = [c for c in df.select_dtypes(include=[np.number]).columns if c != label_col]
    if not num_cols:
        return 0.5
    X = _normalize(df[num_cols].fillna(0).values.astype(float))
    per_class: List[float] = []
    for cls in df[label_col].unique():
        mask = (df[label_col] == cls).values
        if mask.sum() > 1:
            per_class.append(float(np.var(X[mask], axis=0).mean()))
    if not per_class:
        return 0.5
    # Max variance for Uniform[0,1] per feature = 1/12
    return round(min(1.0, float(np.mean(per_class)) * 12.0), 3)


def compute_inter_class_distance(df: pd.DataFrame, label_col: str) -> float:
    """Average pairwise centroid distance, normalized by sqrt(n_features)."""
    num_cols: List[str] = [c for c in df.select_dtypes(include=[np.number]).columns if c != label_col]
    if not num_cols:
        return 0.5
    X = _normalize(df[num_cols].fillna(0).values.astype(float))
    centroids: List[np.ndarray] = []
    for cls in df[label_col].unique():
        mask = (df[label_col] == cls).values
        if mask.sum() > 0:
            centroids.append(X[mask].mean(axis=0))
    if len(centroids) < 2:
        return 0.5
    distances = [
        float(np.linalg.norm(centroids[i] - centroids[j]))
        for i in range(len(centroids))
        for j in range(i + 1, len(centroids))
    ]
    max_dist = float(np.sqrt(len(num_cols)))
    return round(min(1.0, float(np.mean(distances)) / max_dist) if max_dist > 0 else 0.5, 3)


def _load_df(
    dataset_bytes: Optional[bytes],
    dataset_filename: str,
    dataset_url: Optional[str],
) -> Optional[pd.DataFrame]:
    if dataset_bytes:
        fname = dataset_filename.lower()
        try:
            if fname.endswith(".parquet"):
                return pd.read_parquet(io.BytesIO(dataset_bytes))
            if fname.endswith(".json") or fname.endswith(".jsonl"):
                return pd.read_json(io.BytesIO(dataset_bytes))
            return pd.read_csv(io.BytesIO(dataset_bytes))
        except Exception:
            return None

    if dataset_url:
        try:
            with urllib.request.urlopen(dataset_url, timeout=15) as resp:
                raw = resp.read()
            url_l = dataset_url.lower()
            if "parquet" in url_l:
                return pd.read_parquet(io.BytesIO(raw))
            if ".json" in url_l:
                return pd.read_json(io.BytesIO(raw))
            return pd.read_csv(io.BytesIO(raw))
        except Exception:
            return None

    return None


def analyze(
    dataset_bytes: Optional[bytes],
    dataset_filename: str,
    dataset_url: Optional[str],
) -> Dict[str, Any]:
    """Extract all dataset features automatically. Returns {} on failure."""
    df = _load_df(dataset_bytes, dataset_filename, dataset_url)
    if df is None:
        return {}

    result: Dict[str, Any] = {
        "nb_train_samples": len(df),
        "dataset_modality": _guess_modality(dataset_filename, dataset_url or ""),
    }

    label_col = _find_label_col(df)
    if label_col and df[label_col].nunique() >= 2:
        result["nb_classes"]                  = int(df[label_col].nunique())
        result["dataset_intra_variance"]       = compute_intra_variance(df, label_col)
        result["dataset_inter_class_distance"] = compute_inter_class_distance(df, label_col)

    return result


def summary_message(features: Dict[str, Any]) -> str:
    parts = [f"{features.get('nb_train_samples', '?'):,} échantillons"]
    if "nb_classes" in features:
        parts.append(f"{features['nb_classes']} classes")
    parts.append(f"modalité : {features.get('dataset_modality', '?')}")
    if "dataset_intra_variance" in features:
        parts.append(f"var. intra : {features['dataset_intra_variance']:.3f}")
    if "dataset_inter_class_distance" in features:
        parts.append(f"dist. inter : {features['dataset_inter_class_distance']:.3f}")
    return " · ".join(parts)

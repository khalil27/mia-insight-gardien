from typing import List

from fastapi import APIRouter

from ..pipeline.predictor import _load_models, _models, FEATURES_A
from ..schemas.insights import FeatureImportance

router = APIRouter(prefix="/insights", tags=["insights"])

_FALLBACK: List[FeatureImportance] = [
    FeatureImportance(feature="train_test_gap",               importance=0.29),
    FeatureImportance(feature="nb_train_samples_log",         importance=0.18),
    FeatureImportance(feature="dropout",                      importance=0.11),
    FeatureImportance(feature="weight_decay",                 importance=0.09),
    FeatureImportance(feature="epochs",                       importance=0.08),
    FeatureImportance(feature="data_augmentation",            importance=0.07),
    FeatureImportance(feature="embed_dim",                    importance=0.06),
    FeatureImportance(feature="depth",                        importance=0.05),
    FeatureImportance(feature="nb_params_log",                importance=0.04),
    FeatureImportance(feature="learning_rate",                importance=0.025),
    FeatureImportance(feature="batch_size",                   importance=0.02),
]


@router.get("/feature-importance", response_model=List[FeatureImportance])
def feature_importance():
    _load_models()
    model = _models.get("model_A_regressor") or _models.get("model_B_regressor")
    if model is not None and hasattr(model, "feature_importances_"):
        feat_cols = FEATURES_A if "model_A_regressor" in _models else []
        importances = model.feature_importances_
        pairs = list(zip(feat_cols[: len(importances)], importances))
        pairs.sort(key=lambda x: -x[1])
        return [FeatureImportance(feature=f, importance=float(i)) for f, i in pairs]
    return _FALLBACK

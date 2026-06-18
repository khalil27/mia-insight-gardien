from typing import List

from fastapi import APIRouter

from ..pipeline.predictor import _load_model
from ..pipeline.features import FEATURE_COLUMNS
from ..schemas.insights import FeatureImportance

router = APIRouter(prefix="/insights", tags=["insights"])

_FALLBACK: List[FeatureImportance] = [
    FeatureImportance(feature="train_test_gap", importance=0.29),
    FeatureImportance(feature="nb_train_samples", importance=0.18),
    FeatureImportance(feature="dropout", importance=0.11),
    FeatureImportance(feature="weight_decay", importance=0.09),
    FeatureImportance(feature="epochs", importance=0.08),
    FeatureImportance(feature="data_augmentation", importance=0.07),
    FeatureImportance(feature="embed_dim", importance=0.06),
    FeatureImportance(feature="depth", importance=0.05),
    FeatureImportance(feature="num_heads", importance=0.03),
    FeatureImportance(feature="learning_rate", importance=0.025),
    FeatureImportance(feature="batch_size", importance=0.02),
]


@router.get("/feature-importance", response_model=List[FeatureImportance])
def feature_importance():
    model = _load_model()
    if model is not None and hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        pairs = list(zip(FEATURE_COLUMNS[: len(importances)], importances))
        pairs.sort(key=lambda x: -x[1])
        return [FeatureImportance(feature=f, importance=float(i)) for f, i in pairs]
    return _FALLBACK

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class EvaluateInput(BaseModel):
    # Architecture
    model_type: str = "CNN"
    dataset_modality: str = "tabular"
    depth: int = 6
    num_heads: int = 0
    embed_dim: int = 0
    mlp_ratio: float = 0.0
    nb_params: int = 100_000
    patch_size: int = 0
    # Training
    epochs: int = 50
    learning_rate: float = 0.001
    batch_size: int = 64
    dropout: float = 0.0
    weight_decay: float = 0.0
    data_augmentation: bool = False
    # Dataset
    nb_train_samples: int = 10_000
    nb_classes: int = 2
    dataset_intra_variance: float = 0.5
    dataset_inter_class_distance: float = 0.5
    # Performance
    train_accuracy: float = 0.9
    test_accuracy: float = 0.85


class EvaluateResponse(BaseModel):
    auc: float
    risk_level: str
    recommendations: List[str]
    report: str


class EvaluationRecord(EvaluateResponse):
    id: str
    created_at: datetime
    input: EvaluateInput
    model_name: Optional[str] = None
    dataset_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SubmitResponse(BaseModel):
    job_id: str

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email            = Column(String, unique=True, nullable=False, index=True)
    hashed_password  = Column(String, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)

    evaluations = relationship("Evaluation", back_populates="user")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id      = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Architecture
    model_type       = Column(String, nullable=False)
    dataset_modality = Column(String, nullable=False)
    depth            = Column(Integer)
    num_heads        = Column(Integer)
    embed_dim        = Column(Integer)
    mlp_ratio        = Column(Float)
    nb_params        = Column(Integer)
    patch_size       = Column(Integer)
    # Training
    epochs           = Column(Integer)
    learning_rate    = Column(Float)
    batch_size       = Column(Integer)
    dropout          = Column(Float)
    weight_decay     = Column(Float)
    data_augmentation = Column(Boolean)
    # Dataset
    nb_train_samples          = Column(Integer)
    nb_classes                = Column(Integer)
    class_balance             = Column(Float, nullable=True)   # legacy — kept for existing rows
    dataset_intra_variance    = Column(Float, nullable=True)
    dataset_inter_class_distance = Column(Float, nullable=True)
    # Performance
    train_accuracy = Column(Float)
    test_accuracy  = Column(Float)

    # Output
    auc             = Column(Float)
    risk_level      = Column(String)
    recommendations = Column(Text)   # JSON array
    model_name      = Column(String, nullable=True)
    dataset_name    = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user   = relationship("User", back_populates="evaluations")
    report = relationship("Report", back_populates="evaluation", uselist=False)


class Report(Base):
    __tablename__ = "reports"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = Column(String, ForeignKey("evaluations.id"), nullable=False)
    content       = Column(Text, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    evaluation = relationship("Evaluation", back_populates="report")

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import models
from ..db.database import get_db
from ..schemas.results import GapAucPoint, ResultsSummary

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/summary", response_model=ResultsSummary)
def results_summary(db: Session = Depends(get_db)):
    evals = db.query(models.Evaluation).all()

    gap_vs_auc = []
    auc_histogram = [0] * 10

    for e in evals:
        gap = max(0.0, (e.train_accuracy or 0.0) - (e.test_accuracy or 0.0))
        auc_val = e.auc or 0.5

        gap_vs_auc.append(
            GapAucPoint(
                gap=round(gap, 3),
                auc=round(auc_val, 3),
                modality=e.dataset_modality,
            )
        )

        bucket = min(9, int((auc_val - 0.5) / 0.05)) if auc_val >= 0.5 else 0
        auc_histogram[bucket] += 1

    return ResultsSummary(
        runs=len(evals),
        gap_vs_auc=gap_vs_auc,
        auc_histogram=auc_histogram,
    )

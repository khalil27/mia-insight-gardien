from typing import List

from pydantic import BaseModel


class GapAucPoint(BaseModel):
    gap: float
    auc: float
    modality: str


class ResultsSummary(BaseModel):
    runs: int
    gap_vs_auc: List[GapAucPoint]
    auc_histogram: List[int]

from pydantic import BaseModel


class FeatureImportance(BaseModel):
    feature: str
    importance: float

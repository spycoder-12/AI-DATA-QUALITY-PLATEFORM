from typing import List

from pydantic import BaseModel


class HealthResponse(BaseModel):

    status: str

    version: str

    message: str


class QualityResponse(BaseModel):

    rows: int

    columns: int

    missing_values: int

    duplicate_rows: int


class AnomalyResponse(BaseModel):

    row: int

    feature: str

    value: float

    z_score: float

    severity: str

    recommendation: str


class AnalysisResponse(BaseModel):

    filename: str

    rows: int

    columns: int

    anomalies_detected: int

    quality: QualityResponse

    anomalies: List[
        AnomalyResponse
    ]
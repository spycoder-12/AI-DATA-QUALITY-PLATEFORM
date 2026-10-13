from datetime import datetime

from typing import List

from pydantic import BaseModel


# =====================================================
# HEALTH
# =====================================================

class HealthResponse(BaseModel):

    status: str

    version: str

    message: str


# =====================================================
# QUALITY
# =====================================================

class QualityResponse(BaseModel):

    rows: int

    columns: int

    missing_values: int

    duplicate_rows: int


# =====================================================
# ANOMALY
# =====================================================

class AnomalyResponse(BaseModel):

    row: int

    feature: str

    value: float

    z_score: float

    severity: str

    recommendation: str


# =====================================================
# ANALYSIS
# =====================================================

class AnalysisResponse(BaseModel):

    filename: str

    rows: int

    columns: int

    anomalies_detected: int

    quality: QualityResponse

    anomalies: List[
        AnomalyResponse
    ]


# =====================================================
# HISTORY
# =====================================================

class HistoryResponse(BaseModel):

    id: int

    filename: str

    rows: int

    columns: int

    missing_values: int

    duplicate_rows: int

    anomalies_detected: int

    created_at: datetime
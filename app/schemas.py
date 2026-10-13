"""Pydantic request/response models (validated API inputs)."""
from __future__ import annotations

from dataclasses import fields
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import AnalysisConfig


class AnalyzeRequest(BaseModel):
    """Optional settings for one analysis run."""
    model_config = ConfigDict(extra="forbid")
    reference_dataset_id: Optional[int] = Field(None, ge=1, description="Dataset to compare against for drift.")
    auto_reference: bool = Field(True, description="If no reference is given, use the previous upload of the same file name.")
    thresholds: Optional[Dict[str, Any]] = Field(None, description="Override analysis thresholds (see GET /api/config).")
    validity_rules: Optional[Dict[str, List[Optional[float]]]] = Field(
        None, description="Per-column [min, max] validity ranges, e.g. {'age': [0, 120]}.")
    allowed_values: Optional[Dict[str, List[str]]] = Field(
        None, description="Per-column approved category lists.")

    @field_validator("thresholds")
    @classmethod
    def _known_thresholds(cls, value):
        if value:
            valid = {f.name for f in fields(AnalysisConfig)}
            unknown = sorted(set(value) - valid)
            if unknown:
                raise ValueError(f"Unknown threshold(s): {', '.join(unknown)}")
        return value

    @field_validator("validity_rules")
    @classmethod
    def _rule_shape(cls, value):
        for column, rule in (value or {}).items():
            if len(rule) != 2:
                raise ValueError(f"Rule for '{column}' must be [min, max] (use null for no bound).")
        return value


class RemediationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: Optional[List[str]] = Field(
        None, description="Operations to apply. Omit to apply only the safe fixes.")
    numeric_strategy: Optional[str] = Field(None, description="median | mean | zero | drop_rows | none")
    categorical_strategy: Optional[str] = Field(None, description="mode | unknown | drop_rows | none")
    winsorize_multiplier: Optional[float] = Field(None, gt=0, le=10)


class DriftCompareRequest(BaseModel):
    reference_dataset_id: int = Field(ge=1)
    current_dataset_id: int = Field(ge=1)


class DatasetOut(BaseModel):
    id: int
    name: str
    file_type: str
    size_bytes: int
    rows: int
    columns: int
    is_reference: bool
    uploaded_at: str
    analyses: int = 0
    latest_analysis: Optional[Dict[str, Any]] = None

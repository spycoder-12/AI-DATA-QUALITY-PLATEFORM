"""ORM models.

Only what the platform needs is stored: dataset *metadata* (the file itself
stays on disk), analysis results and flagged records. Full raw datasets are
never copied into the database.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String,
                        Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.helpers import utcnow


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(80), unique=True)
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    group_key: Mapped[str] = mapped_column(String(255), index=True)   # dataset series (same file name)
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    rows: Mapped[int] = mapped_column(Integer, default=0)
    columns: Mapped[int] = mapped_column(Integer, default=0)
    load_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan",
        foreign_keys="AnalysisRun.dataset_id")


class AnalysisRun(Base):
    """One analysis run == one monitoring point (history) + the full unified result."""
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    reference_dataset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")   # QUEUED|RUNNING|COMPLETED|FAILED
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # ---- quality results / monitoring columns
    rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    columns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    missing_values: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duplicate_rows: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anomaly_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anomaly_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    critical_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    drifted_features: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # NULL = not assessed
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    overall_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    alert_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trend: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)              # unified result
    dataset: Mapped[Dataset] = relationship(back_populates="runs", foreign_keys=[dataset_id])
    anomalies: Mapped[list["Anomaly"]] = relationship(cascade="all, delete-orphan", back_populates="run")
    alerts: Mapped[list["Alert"]] = relationship(cascade="all, delete-orphan", back_populates="run")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        cascade="all, delete-orphan", back_populates="run")
    remediations: Mapped[list["RemediationRun"]] = relationship(
        cascade="all, delete-orphan", back_populates="run")


class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    evidence_level: Mapped[str] = mapped_column(String(10))
    support_count: Mapped[int] = mapped_column(Integer)
    detectors: Mapped[str] = mapped_column(String(200))
    primary_feature: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    primary_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # only flagged features/values
    run: Mapped[AnalysisRun] = relationship(back_populates="anomalies")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[int] = mapped_column(Integer, index=True)
    alert_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), index=True)
    message: Mapped[str] = mapped_column(Text)
    affected: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metric: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="ACTIVE")      # ACTIVE | ACKNOWLEDGED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    run: Mapped[AnalysisRun] = relationship(back_populates="alerts")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    priority: Mapped[str] = mapped_column(String(4))
    target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    finding: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    automated_fix: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    run: Mapped[AnalysisRun] = relationship(back_populates="recommendations")


class RemediationRun(Base):
    __tablename__ = "remediation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cleaned_filename: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    run: Mapped[AnalysisRun] = relationship(back_populates="remediations")


Index("ix_runs_dataset_completed", AnalysisRun.dataset_id, AnalysisRun.completed_at)

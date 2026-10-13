from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text
)

from sqlalchemy.orm import relationship

from app.database import Base


# =====================================================
# ANALYSIS TABLE
# =====================================================

class Analysis(Base):

    __tablename__ = "analyses"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    filename = Column(
        String(255),
        nullable=False
    )


    rows = Column(
        Integer,
        nullable=False
    )


    columns = Column(
        Integer,
        nullable=False
    )


    missing_values = Column(
        Integer,
        default=0
    )


    duplicate_rows = Column(
        Integer,
        default=0
    )


    anomalies_detected = Column(
        Integer,
        default=0
    )


    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


    anomalies = relationship(
        "Anomaly",
        back_populates="analysis",
        cascade="all, delete-orphan"
    )


# =====================================================
# ANOMALY TABLE
# =====================================================

class Anomaly(Base):

    __tablename__ = "anomalies"


    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    analysis_id = Column(
        Integer,
        ForeignKey(
            "analyses.id"
        ),
        nullable=False
    )


    row_number = Column(
        Integer,
        nullable=False
    )


    feature = Column(
        String(255),
        nullable=False
    )


    value = Column(
        Float,
        nullable=False
    )


    z_score = Column(
        Float,
        nullable=False
    )


    severity = Column(
        String(50),
        nullable=False
    )


    recommendation = Column(
        Text,
        nullable=False
    )


    analysis = relationship(
        "Analysis",
        back_populates="anomalies"
    )
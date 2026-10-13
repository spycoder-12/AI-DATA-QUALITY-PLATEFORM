import os

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    DateTime
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# DATABASE URL
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:

    raise ValueError(
        "DATABASE_URL is not configured in .env"
    )


# ============================================================
# ENGINE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


# ============================================================
# BASE
# ============================================================

Base = declarative_base()


# ============================================================
# MONITORING RUN TABLE
# ============================================================

class MonitoringRun(Base):

    __tablename__ = "monitoring_runs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    quality_score = Column(
        Float,
        nullable=False
    )

    anomaly_count = Column(
        Integer,
        default=0
    )

    drifted_features = Column(
        Integer,
        default=0
    )

    alerts = Column(
        Integer,
        default=0
    )

    risk_score = Column(
        Float,
        default=0
    )

    risk_level = Column(
        String(50)
    )

    status = Column(
        String(50)
    )

    decision = Column(
        String(255)
    )

    created_at = Column(
        DateTime
    )


# ============================================================
# UPLOADED DATASET TABLE
# ============================================================

class UploadedDataset(Base):

    __tablename__ = "uploaded_datasets"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    original_filename = Column(
        String(255),
        nullable=False
    )

    stored_filename = Column(
        String(255),
        nullable=False
    )

    file_type = Column(
        String(20)
    )

    rows = Column(
        Integer,
        default=0
    )

    columns = Column(
        Integer,
        default=0
    )

    missing_values = Column(
        Integer,
        default=0
    )

    duplicate_rows = Column(
        Integer,
        default=0
    )

    anomaly_count = Column(
        Integer,
        default=0
    )

    completeness = Column(
        Float,
        default=0
    )

    quality_score = Column(
        Float,
        default=0
    )

    risk_level = Column(
        String(50)
    )

    uploaded_at = Column(
        DateTime
    )


# ============================================================
# SESSION
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================
# DATABASE SESSION
# ============================================================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()
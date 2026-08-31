import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    CHAR,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import JSON, TypeDecorator, CHAR as SQLAlchemyCHAR
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = SQLAlchemyCHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(SQLAlchemyCHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value) if not isinstance(value, uuid.UUID) else value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


from sqlalchemy import Integer

# Cross-compatible BigInt PK type (BIGINT on Postgres, INTEGER on SQLite for AUTOINCREMENT)
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
# Cross-compatible JSONB type
JSONType = JSON().with_variant(JSONB, "postgresql")


class Call(Base):
    __tablename__ = "calls"

    call_id = Column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active", server_default=text("'active'"))

    __table_args__ = (
        CheckConstraint("source IN ('mic', 'phone_sim', 'replay')", name="ck_calls_source"),
        CheckConstraint("status IN ('active', 'stopped')", name="ck_calls_status"),
    )

    # Relationships
    detections = relationship("Detection", back_populates="call", cascade="all, delete-orphan")
    holds = relationship("TransactionHold", back_populates="call", cascade="all, delete-orphan")
    evidence_logs = relationship("EvidenceLog", back_populates="call", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    detection_id = Column(BigIntPK, primary_key=True, autoincrement=True)
    call_id = Column(
        GUID,
        ForeignKey("calls.call_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_start_ms = Column(BigInteger, nullable=False)
    window_end_ms = Column(BigInteger, nullable=False)
    spoof_probability = Column(Float, nullable=False)
    fused_risk_score = Column(Float, nullable=False)
    is_flagged = Column(Boolean, nullable=False)
    model_version = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("spoof_probability >= 0.0 AND spoof_probability <= 1.0", name="ck_detections_spoof_prob"),
        CheckConstraint("fused_risk_score >= 0.0 AND fused_risk_score <= 1.0", name="ck_detections_fused_risk"),
        CheckConstraint("window_end_ms > window_start_ms", name="ck_detections_window_range"),
    )

    # Relationships
    call = relationship("Call", back_populates="detections")
    holds = relationship("TransactionHold", back_populates="detection")
    evidence_logs = relationship("EvidenceLog", back_populates="detection")


class TransactionHold(Base):
    __tablename__ = "transaction_holds"

    hold_id = Column(BigIntPK, primary_key=True, autoincrement=True)
    call_id = Column(
        GUID,
        ForeignKey("calls.call_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by = Column(
        BigInteger,
        ForeignKey("detections.detection_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    triggered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    mock_reference = Column(Text, nullable=False)

    # Relationships
    call = relationship("Call", back_populates="holds")
    detection = relationship("Detection", back_populates="holds")


class EvidenceLog(Base):
    __tablename__ = "evidence_log"

    entry_id = Column(BigIntPK, primary_key=True, autoincrement=True)
    call_id = Column(
        GUID,
        ForeignKey("calls.call_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detection_id = Column(
        BigInteger,
        ForeignKey("detections.detection_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload = Column(JSONType, nullable=False)
    entry_hash = Column(CHAR(64), nullable=False)
    prev_hash = Column(CHAR(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    call = relationship("Call", back_populates="evidence_logs")
    detection = relationship("Detection", back_populates="evidence_logs")

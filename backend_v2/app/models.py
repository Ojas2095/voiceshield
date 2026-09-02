"""
SQLAlchemy ORM models — mirrors the PostgreSQL schema from §6 of the brief.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Call(Base):
    __tablename__ = "calls"

    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("source IN ('mic','phone_sim','replay')", name="ck_calls_source"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint(
            "status IN ('active','ended','held')", name="ck_calls_status"
        ),
        server_default="active",
        nullable=False,
    )

    detections: Mapped[list["Detection"]] = relationship(
        "Detection", back_populates="call", cascade="all, delete-orphan"
    )
    holds: Mapped[list["TransactionHold"]] = relationship(
        "TransactionHold", back_populates="call", cascade="all, delete-orphan"
    )
    evidence_entries: Mapped[list["EvidenceLog"]] = relationship(
        "EvidenceLog", back_populates="call", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    detection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False
    )
    window_start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    window_end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    spoof_probability: Mapped[float] = mapped_column(Float, nullable=False)
    fused_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verdict: Mapped[str] = mapped_column(
        String(12),
        CheckConstraint(
            "verdict IN ('REAL','SUSPICIOUS','FRAUD')", name="ck_detections_verdict"
        ),
        nullable=False,
        default="REAL",
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    call: Mapped["Call"] = relationship("Call", back_populates="detections")
    hold: Mapped["TransactionHold | None"] = relationship(
        "TransactionHold", back_populates="triggering_detection", uselist=False
    )
    evidence_entries: Mapped[list["EvidenceLog"]] = relationship(
        "EvidenceLog", back_populates="detection"
    )


class TransactionHold(Base):
    __tablename__ = "transaction_holds"

    hold_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False
    )
    triggered_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("detections.detection_id"), nullable=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    mock_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    call: Mapped["Call"] = relationship("Call", back_populates="holds")
    triggering_detection: Mapped["Detection | None"] = relationship(
        "Detection", back_populates="hold"
    )


class EvidenceLog(Base):
    __tablename__ = "evidence_log"

    entry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False
    )
    detection_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("detections.detection_id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Ed25519 signature over entry_hash (non-repudiation); nullable for legacy rows.
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    call: Mapped["Call"] = relationship("Call", back_populates="evidence_entries")
    detection: Mapped["Detection | None"] = relationship(
        "Detection", back_populates="evidence_entries"
    )

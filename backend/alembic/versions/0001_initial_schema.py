"""Initial schema with pgcrypto, calls, detections, transaction_holds, and evidence_log

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-31 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgcrypto extension for gen_random_uuid() if on PostgreSQL
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # 2. Create calls table
    op.create_table(
        "calls",
        sa.Column("call_id", postgresql.UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(36), server_default=sa.text("gen_random_uuid()") if conn.dialect.name == "postgresql" else None, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.CheckConstraint("source IN ('mic', 'phone_sim', 'replay')", name="ck_calls_source"),
        sa.CheckConstraint("status IN ('active', 'stopped')", name="ck_calls_status"),
        sa.PrimaryKeyConstraint("call_id", name="pk_calls"),
    )

    # 3. Create detections table
    op.create_table(
        "detections",
        sa.Column("detection_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(36), nullable=False),
        sa.Column("window_start_ms", sa.BigInteger(), nullable=False),
        sa.Column("window_end_ms", sa.BigInteger(), nullable=False),
        sa.Column("spoof_probability", sa.Float(), nullable=False),
        sa.Column("fused_risk_score", sa.Float(), nullable=False),
        sa.Column("is_flagged", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("spoof_probability >= 0.0 AND spoof_probability <= 1.0", name="ck_detections_spoof_prob"),
        sa.CheckConstraint("fused_risk_score >= 0.0 AND fused_risk_score <= 1.0", name="ck_detections_fused_risk"),
        sa.CheckConstraint("window_end_ms > window_start_ms", name="ck_detections_window_range"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.call_id"], name="fk_detections_call_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("detection_id", name="pk_detections"),
    )
    op.create_index("ix_detections_call_id", "detections", ["call_id"], unique=False)

    # 4. Create transaction_holds table
    op.create_table(
        "transaction_holds",
        sa.Column("hold_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(36), nullable=False),
        sa.Column("triggered_by", sa.BigInteger(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("mock_reference", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.call_id"], name="fk_transaction_holds_call_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["detections.detection_id"], name="fk_transaction_holds_triggered_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("hold_id", name="pk_transaction_holds"),
    )
    op.create_index("ix_transaction_holds_call_id", "transaction_holds", ["call_id"], unique=False)
    op.create_index("ix_transaction_holds_triggered_by", "transaction_holds", ["triggered_by"], unique=False)

    # 5. Create evidence_log table
    op.create_table(
        "evidence_log",
        sa.Column("entry_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(36), nullable=False),
        sa.Column("detection_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON(), nullable=False),
        sa.Column("entry_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("prev_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.call_id"], name="fk_evidence_log_call_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.detection_id"], name="fk_evidence_log_detection_id", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("entry_id", name="pk_evidence_log"),
    )
    op.create_index("ix_evidence_log_call_id", "evidence_log", ["call_id"], unique=False)
    op.create_index("ix_evidence_log_detection_id", "evidence_log", ["detection_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evidence_log_detection_id", table_name="evidence_log")
    op.drop_index("ix_evidence_log_call_id", table_name="evidence_log")
    op.drop_table("evidence_log")

    op.drop_index("ix_transaction_holds_triggered_by", table_name="transaction_holds")
    op.drop_index("ix_transaction_holds_call_id", table_name="transaction_holds")
    op.drop_table("transaction_holds")

    op.drop_index("ix_detections_call_id", table_name="detections")
    op.drop_table("detections")

    op.drop_table("calls")

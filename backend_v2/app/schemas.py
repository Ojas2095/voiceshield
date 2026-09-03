"""
Pydantic request/response schemas for all API endpoints.
"""
import uuid
from datetime import datetime
from typing import Literal

from app.config import get_settings
from pydantic import BaseModel, Field


def to_verdict(risk_score: float) -> str:
    """Convert a fused risk score (0–1) to a canonical three-state verdict.

    Thresholds are driven by config.py (hold_threshold and flag_threshold)
    to ensure consistency across the backend, evidence chain, and frontend.
    """
    _settings = get_settings()
    if risk_score >= _settings.hold_threshold:
        return "FRAUD"
    if risk_score >= _settings.flag_threshold:
        return "SUSPICIOUS"
    return "REAL"


# ── Calls ────────────────────────────────────────────────────────────────────

class StartCallRequest(BaseModel):
    source: str = Field(..., pattern="^(mic|phone_sim|replay)$")


class StartCallResponse(BaseModel):
    call_id: uuid.UUID
    started_at: datetime
    status: str


class CallStatusResponse(BaseModel):
    call_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    source: str
    status: str


# ── WebSocket messages ────────────────────────────────────────────────────────

class RiskUpdate(BaseModel):
    type: str = "risk_update"
    window_start_ms: int
    window_end_ms: int
    spoof_probability: float
    fused_risk_score: float
    is_flagged: bool
    verdict: Literal["REAL", "SUSPICIOUS", "FRAUD"]  # canonical graded state
    vad_active: bool = True
    model_version: str
    language_detected: str = "unknown"  # populated by Layer 2 (ASR) when available
    # ── Layer 2 & 3 fields (populated once ASR + intent + signals are run) ───
    intent_risk: float = 0.0
    call_signal_risk: float = 0.0
    matched_reasons: list[str] = []    # human-readable evidence for the UI
    # ── Explainability & 3-way classification fields ─────────────────────────
    transcript: str = ""
    voice_classification: Literal["HUMAN", "SYNTHETIC"] = "HUMAN"
    scam_risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    threat_category: Literal["LEGITIMATE_HUMAN", "HUMAN_VISHING", "AI_SYNTHETIC"] = "LEGITIMATE_HUMAN"
    acoustic_features: dict[str, float] = {}


class HoldTriggered(BaseModel):
    type: str = "hold_triggered"
    hold_id: int
    triggered_at: datetime
    mock_reference: str
    verdict: Literal["REAL", "SUSPICIOUS", "FRAUD"] = "FRAUD"


class VADUpdate(BaseModel):
    type: str = "vad_update"
    vad_active: bool
    timestamp_ms: int


# ── Transaction Hold ──────────────────────────────────────────────────────────

class HoldResponse(BaseModel):
    hold_id: int
    call_id: uuid.UUID
    triggered_at: datetime
    mock_reference: str
    triggered_by_detection_id: int | None = None


# ── Evidence ─────────────────────────────────────────────────────────────────

class EvidenceEntry(BaseModel):
    entry_id: int
    call_id: uuid.UUID
    detection_id: int | None
    payload: dict
    entry_hash: str
    prev_hash: str
    signature: str | None = None
    created_at: datetime


class EvidenceResponse(BaseModel):
    call_id: uuid.UUID
    chain_valid: bool          # SHA-256 hash-chain integrity (tamper-evident)
    signatures_valid: bool     # Ed25519 signatures verified (non-repudiation)
    public_key: str            # server Ed25519 public key (hex) for independent verification
    entry_count: int
    entries: list[EvidenceEntry]


# ── Detection ─────────────────────────────────────────────────────────────────

class DetectionOut(BaseModel):
    detection_id: int
    call_id: uuid.UUID
    window_start_ms: int
    window_end_ms: int
    spoof_probability: float
    fused_risk_score: float
    is_flagged: bool
    model_version: str
    created_at: datetime

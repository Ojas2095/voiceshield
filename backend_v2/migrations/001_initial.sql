-- VoiceShield PostgreSQL Schema (§6 of the Round 2 brief)
-- Run with: psql -U voiceshield -d voiceshield -f migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── calls ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calls (
    call_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    source      TEXT        NOT NULL CHECK (source IN ('mic', 'phone_sim', 'replay')),
    status      TEXT        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'ended', 'held'))
);

-- ── detections ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS detections (
    detection_id      BIGSERIAL    PRIMARY KEY,
    call_id           UUID         NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    window_start_ms   INTEGER      NOT NULL,
    window_end_ms     INTEGER      NOT NULL,
    spoof_probability REAL         NOT NULL,
    fused_risk_score  REAL         NOT NULL,
    is_flagged        BOOLEAN      NOT NULL,
    -- Canonical three-state verdict (REAL / SUSPICIOUS / FRAUD).
    -- Derived from fused_risk_score via to_verdict(); stored here so the
    -- evidence chain is self-contained for BSA 2023 §63 admissibility.
    verdict           TEXT         NOT NULL DEFAULT 'REAL'
                      CHECK (verdict IN ('REAL','SUSPICIOUS','FRAUD')),
    model_version     TEXT         NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
    -- NOTE: raw audio is NEVER stored here or anywhere (DPDP Act 2023 — voice
    -- is biometric data). Only hashes + scores + metadata are persisted.
);

CREATE INDEX IF NOT EXISTS idx_detections_call_id ON detections(call_id);
CREATE INDEX IF NOT EXISTS idx_detections_flagged  ON detections(call_id) WHERE is_flagged;

-- ── transaction_holds ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transaction_holds (
    hold_id         BIGSERIAL    PRIMARY KEY,
    call_id         UUID         NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    triggered_by    BIGINT       REFERENCES detections(detection_id),
    triggered_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    mock_reference  TEXT                  -- stand-in for real bank/telecom case ID
);

CREATE INDEX IF NOT EXISTS idx_holds_call_id ON transaction_holds(call_id);

-- ── evidence_log (hash-chain) ────────────────────────────────────────────────
-- entry_hash = SHA-256( prev_hash_bytes || canonical_json(payload) )
-- prev_hash for the first entry of each call is '0' * 64 (GENESIS_HASH)
-- Tamper with any past row → every subsequent hash breaks → chain_valid = false
CREATE TABLE IF NOT EXISTS evidence_log (
    entry_id     BIGSERIAL    PRIMARY KEY,
    call_id      UUID         NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    detection_id BIGINT       REFERENCES detections(detection_id),
    payload      JSONB        NOT NULL,   -- all fields used in the hash
    entry_hash   CHAR(64)     NOT NULL,   -- SHA-256 hex digest
    prev_hash    CHAR(64)     NOT NULL,   -- previous entry's hash (or genesis)
    signature    TEXT,                    -- Ed25519 signature over entry_hash (hex), non-repudiation
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_call_id ON evidence_log(call_id);
CREATE INDEX IF NOT EXISTS idx_evidence_call_id_entry ON evidence_log(call_id, entry_id);

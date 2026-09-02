-- 002 — add Ed25519 signature to the evidence chain.
-- Signing each entry_hash gives non-repudiation on top of the SHA-256 chain's
-- tamper-evidence (BSA 2023 §63 "unalterable custody"). Run on existing DBs;
-- fresh installs already get this column from 001_initial.sql.
ALTER TABLE evidence_log ADD COLUMN IF NOT EXISTS signature TEXT;

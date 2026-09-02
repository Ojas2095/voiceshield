"""
VoiceShield backend configuration.
All values can be overridden via environment variables or a .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),  # allow model_* field names without warnings
    )

    # ── Database ────────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://voiceshield:voiceshield@localhost:5432/voiceshield"

    # ── Model ───────────────────────────────────────────────────────────────────
    # wav2vec2-base (768-dim) — fast enough for real-time inference.
    # For multilingual/accuracy at higher latency, switch to facebook/wav2vec2-large-xlsr-53.
    # IMPORTANT: training (ai/train) must use the SAME checkpoint or head dims won't match.
    model_checkpoint: str = "facebook/wav2vec2-base"
    model_weights_path: str | None = None          # None → use DummyClassifier
    use_dummy_classifier: bool = True              # flip to False once weights land

    # ── Inference ───────────────────────────────────────────────────────────────
    inference_workers: int = 2
    sample_rate: int = 16_000                      # internal sample rate (Hz)
    telephony_sample_rate: int = 8_000             # 8 kHz PSTN simulation

    # ── Sliding window ──────────────────────────────────────────────────────────
    window_duration_ms: int = 2_000               # 2 s window
    hop_duration_ms: int = 500                    # 500 ms hop

    # ── Risk thresholds ─────────────────────────────────────────────────────────
    flag_threshold: float = 0.60                  # single-window flag
    hold_threshold: float = 0.70                  # rolling average → trigger hold
    rolling_window_count: int = 5                 # windows to average for rolling score

    # ── Server ──────────────────────────────────────────────────────────────────
    app_name: str = "VoiceShield"
    debug: bool = False

    # ── Model version tag (baked into every detection row) ──────────────────────
    model_version: str = "dummy-v0"

    # ── Evidence signing (Ed25519) ──────────────────────────────────────────────
    # Private key path; auto-generated on first use if absent. Use a KMS/HSM in prod.
    evidence_key_path: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

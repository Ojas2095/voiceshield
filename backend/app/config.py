import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VoiceShield Fraud Detection Engine"
    API_V1_STR: str = "/api"
    
    # Security / Auth
    SECRET_KEY: str = "super-secret-key-change-in-production-voiceshield-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEMO_CLIENT_ID: str = "demo_user"
    DEMO_CLIENT_SECRET: str = "demo_password"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Model Settings
    USE_DUMMY_MODEL: bool = True
    MODEL_WEIGHTS_DIR: str = "./ai/models"
    WAV2VEC_MODEL_NAME: str = "facebook/wav2vec2-large-xlsr-53"

    # Risk Fusion Settings
    RISK_THRESHOLD: float = 0.70

    # Layer 2 (conversation intent). ASR is heavy — off by default so the
    # realtime path stays light; enable on a machine with Whisper installed.
    ENABLE_LAYER2_ASR: bool = False
    ASR_EVERY_N_WINDOWS: int = 3

    # Database (PostgreSQL in production, sqlite for local tests)
    DATABASE_URL: str = "sqlite+aiosqlite:///./voiceshield.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

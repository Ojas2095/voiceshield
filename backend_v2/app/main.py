"""
VoiceShield FastAPI application entry point.

Lifecycle:
  startup → load classifier (DummyClassifier or VoiceShieldClassifier) + warm up
  shutdown → nothing special needed (DB pool handled by SQLAlchemy)

CORS is intentionally open during development (origin=*).
Tighten before any production/staging deployment.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.inference as inf
from app.config import get_settings
from app.routers import calls, evidence, websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """FastAPI lifespan — runs once at startup, then yields for the app lifetime."""
    logger.info("=== VoiceShield starting up ===")
    
    # Ensure database tables exist
    try:
        from app.database import Base, engine
        import app.models  # load models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized.")
    except Exception as e:
        logger.warning("Could not auto-create tables: %s", e)

    inf.classifier = inf.load_classifier()
    logger.info(
        "Classifier ready: %s on %s",
        type(inf.classifier).__name__,
        getattr(inf.classifier, "device", "cpu"),
    )
    yield
    logger.info("=== VoiceShield shutting down ===")


app = FastAPI(
    title="VoiceShield API",
    description=(
        "Real-time AI voice-clone fraud detection. "
        "DETECT → PREVENT → PROVE pipeline."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(calls.router)
app.include_router(evidence.router)
app.include_router(websocket.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Quick liveness check — also reports which classifier is loaded."""
    clf = inf.classifier
    return {
        "status": "ok",
        "classifier": type(clf).__name__ if clf else "not_loaded",
        "model_version": getattr(clf, "model_version", "unknown"),
    }

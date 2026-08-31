import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.middleware import SecurityHeadersMiddleware

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("voiceshield")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifespan context manager for startup and shutdown events.
    """
    logger.info("Initializing VoiceShield Application Services...")
    from backend.app.inference import get_classifier
    app.state.classifier = get_classifier()
    logger.info(f"Loaded classifier model: {app.state.classifier.__class__.__name__}")
    
    yield
    
    logger.info("Shutting down VoiceShield Application Services...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="VoiceShield Real-Time AI Voice-Cloning Fraud Detection Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Apply Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Enforce strict CORS restricted to http://localhost:3000 only (no wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and WebSocket Routers
from backend.app.security.auth import router as auth_router
from backend.app.routers.calls import router as calls_router
from backend.app.routers.evidence import router as evidence_router
from backend.app.routers.prevent import router as prevent_router
from backend.app.websocket import router as ws_router

app.include_router(auth_router)
app.include_router(calls_router)
app.include_router(evidence_router)
app.include_router(prevent_router)
app.include_router(ws_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler masking internal errors and tracebacks from client responses.
    Logs full exception server-side.
    """
    logger.exception(f"Unhandled internal exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "VoiceShield AI Fraud Detection API"}

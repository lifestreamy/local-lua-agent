"""
api/main.py — FastAPI application entry point.

Startup sequence:
  1. FastAPI app created.
  2. On startup event: OllamaClient.warm_up() called — blocks until model is
     loaded in VRAM. Uvicorn prints "Model ready" before accepting requests.
  3. All subsequent /generate calls are fast (model already in VRAM).

POST /generate
  Body:    {"prompt": "<natural language task>"}
  Returns: {"code":   "<raw Lua string>"}
"""

import logging
import asyncio

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.agent import AgentPipeline, OllamaClient
from api.models import GenerateRequest, GenerateResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Single shared instances — created once, reused for all requests
_ollama_client = OllamaClient()
_pipeline = AgentPipeline(ollama_client=_ollama_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager — replaces deprecated @app.on_event("startup").
    Runs warm_up() before uvicorn starts accepting requests.
    """
    logger.info("=" * 60)
    logger.info("LocalScript API starting up...")
    logger.info("Warming up model — loading into VRAM, please wait...")
    try:
        # Run blocking warm-up in thread pool so we don't block the event loop
        await asyncio.to_thread(_ollama_client.warm_up)
        logger.info("Model ready. Server accepting requests.")
    except Exception as exc:
        logger.warning("Warm-up failed (non-fatal): %s. Will retry on first request.", exc)
    logger.info("=" * 60)
    yield
    # Shutdown
    logger.info("LocalScript API shutting down.")


app = FastAPI(
    title="LocalScript API",
    description="Local agentic Lua code generator for MWS Octapi LowCode platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Quick liveness check. Returns 200 once model is warmed up."""
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """
    Generate Lua code from a natural language prompt (Russian or English).
    Model is guaranteed to be in VRAM before this is called (startup warm-up).
    """
    logger.info("POST /generate prompt=%r", request.prompt[:80])
    try:
        code = _pipeline.generate(request.prompt)
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc
    return GenerateResponse(code=code)

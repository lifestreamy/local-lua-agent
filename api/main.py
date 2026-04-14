"""
api/main.py — FastAPI application entry point.

Exposes:
  GET  /health   — dynamic liveness check (checks Ollama status)
  POST /generate — Lua code generation from natural language prompt

Port: 8080 (as per localscript-openapi.yaml).
Launched by: uvicorn api.main:app --host 0.0.0.0 --port 8080
"""

import logging
import httpx

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.agent import AgentPipeline, OLLAMA_BASE_URL, OLLAMA_MODEL
from api.guard import is_safe_prompt, sanitize_output
from api.models import GenerateRequest, GenerateResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LocalScript API",
    description="Local agentic Lua code generator for MWS Octapi LowCode platform.",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_pipeline = AgentPipeline()
SECURITY_FALLBACK = "return nil -- [SECURITY_BLOCK] Unsafe or off-topic prompt detected"


@app.get("/health")
async def health() -> JSONResponse:
    """
    Dynamic liveness check.
    Returns 200 OK if FastAPI is up AND Ollama has the required model available.
    Returns 503 if Ollama is unreachable or the model is missing.
    """
    try:
        # Check if Ollama is responding and has our specific model
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()

            models = resp.json().get("models", [])
            model_names = [m.get("name") for m in models]

            if OLLAMA_MODEL in model_names:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "status": "ok",
                        "model": OLLAMA_MODEL,
                        "ollama": "connected"
                    }
                )
            else:
                logger.warning(f"Healthcheck failed: {OLLAMA_MODEL} not found in Ollama.")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "error",
                        "detail": f"Model {OLLAMA_MODEL} not pulled yet"
                    }
                )

    except httpx.RequestError as exc:
        logger.error(f"Healthcheck failed: Ollama unreachable. {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "detail": "Ollama service is unreachable"
            }
        )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    logger.info(
        "POST /generate prompt=%r has_context=%s",
        request.prompt[:80],
        bool(request.context),
    )

    is_safe = await is_safe_prompt(request, OLLAMA_BASE_URL, OLLAMA_MODEL)
    if not is_safe:
        logger.warning("Unsafe prompt intercepted. Returning safe fallback Lua.")
        return GenerateResponse(code=SECURITY_FALLBACK)

    try:
        code = _pipeline.generate(request)
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    code = sanitize_output(code)
    return GenerateResponse(code=code)
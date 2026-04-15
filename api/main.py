"""
api/main.py — FastAPI application entry point.

Exposes:
  GET  /health   — dynamic liveness check (checks Ollama status + verbose info)
  POST /generate — Async Lua code generation task submission
  GET  /status   — SSE stream for task status polling

Port: 8080.
"""

import logging
import uuid
import asyncio
import httpx
import json

from fastapi import FastAPI, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from api.agent import AgentPipeline, OLLAMA_BASE_URL, OLLAMA_MODEL
from api.guard import is_safe_prompt, sanitize_output
from api.models import GenerateRequest, TaskSubmitResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LocalScript API",
    description="Local agentic Lua code generator for MWS Octapi LowCode platform.",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = AgentPipeline()
SECURITY_FALLBACK = "return nil -- [SECURITY_BLOCK] Unsafe or off-topic prompt detected"

# Hard limit for rolling context to prevent OOM
MAX_CONTEXT_CHARS = 4096

TASKS: dict[str, dict] = {}


@app.get("/health")
async def health() -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()

            models = resp.json().get("models", [])
            model_names = [m.get("name") for m in models]

            if OLLAMA_MODEL in model_names:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={"status": "ok", "model": OLLAMA_MODEL, "ollama": "connected"}
                )
            else:
                logger.warning(f"Healthcheck failed: {OLLAMA_MODEL} not found in Ollama.")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "error", "detail": f"Model {OLLAMA_MODEL} not pulled yet"}
                )

    except httpx.RequestError as exc:
        logger.error(f"Healthcheck failed: Ollama unreachable. {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "detail": "Ollama service is unreachable"}
        )


async def run_pipeline_task(task_id: str, request: GenerateRequest):
    task = TASKS[task_id]
    queue = task["queue"]

    async def put_status(stage: str, message: str = "", code: str = "", error: str = ""):
        task["status"] = stage
        if stage in ("done", "error"):
            task["final_code"] = code
        await queue.put({"stage": stage, "message": message, "code": code, "error": error})

    try:
        # 0. Enforce Server-Side Trimming
        if request.context and len(request.context) > MAX_CONTEXT_CHARS:
            logger.warning("Trimming context for task %s from %d to %d chars.", task_id, len(request.context), MAX_CONTEXT_CHARS)
            # Keep the most recent part of the history (the end of the string)
            request.context = "..." + request.context[-(MAX_CONTEXT_CHARS - 3):]

        # 1. Run the Security Guard First
        await put_status("pending", message="Проверка безопасности промпта...")

        is_safe = await is_safe_prompt(request, OLLAMA_BASE_URL, OLLAMA_MODEL)
        if not is_safe:
            logger.warning("Unsafe prompt intercepted for task %s.", task_id)
            await put_status("done", message="Запрос заблокирован системой безопасности.", code=SECURITY_FALLBACK)
            return

        # 2. Consume the Async Agent Pipeline
        async for status_update in _pipeline.generate_stream(request):
            if status_update.get("code"):
                status_update["code"] = sanitize_output(status_update["code"])

            await put_status(
                stage=status_update["stage"],
                message=status_update["message"],
                code=status_update["code"],
                error=status_update["error"]
            )

    except Exception as exc:
        logger.exception("Task %s pipeline error: %s", task_id, exc)
        await put_status("error", message="Внутренняя ошибка сервера", error=str(exc))
    finally:
        await queue.put(None)


@app.post("/generate", response_model=TaskSubmitResponse)
async def generate_submit(request: GenerateRequest, background_tasks: BackgroundTasks):
    logger.info("POST /generate prompt=%r has_context=%s", request.prompt[:80], bool(request.context))

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "status": "pending",
        "final_code": "",
        "queue": asyncio.Queue()
    }

    background_tasks.add_task(run_pipeline_task, task_id, request)
    return TaskSubmitResponse(task_id=task_id)


@app.get("/status")
async def get_status(request: Request, task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    task = TASKS[task_id]
    queue = task["queue"]

    if task["status"] in ("done", "error"):
        async def fast_stream():
            yield {"data": json.dumps({"stage": task["status"], "message": "", "code": task["final_code"], "error": ""})}
        return EventSourceResponse(fast_stream())

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                update = await queue.get()
                if update is None:
                    break
                yield {"data": json.dumps(update)}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())

"""
api/agent.py — Async Ollama client and AgentPipeline for SSE streaming.

Pipeline steps (Asynchronous & SSE Ready):
1. Build prompt (system_prompt + optional rolling context + user task).
2. Yield 'generating' status to SSE stream.
3. POST asynchronously to Ollama /api/generate.
4. Extract Lua code and LLM conversational message (e.g., from <thinking> tags).
5. If no code is found, assume Clarification Loop -> Yield 'done' with message, exit.
6. Yield 'validating' status.
7. Validate with luac (run synchronously in a thread pool).
8. If valid -> Yield 'done' with code and message, exit.
9. If invalid -> Yield 'retrying' with error, rebuild prompt, go to 3.
10. After MAX_RETRIES -> Yield 'error' with best code.

Response format expected from LLM:
<thinking>
  ...reasoning or clarifying question...
</thinking>
<code>
  ...raw lua code...
</code>
"""

import logging
import os
import re
import asyncio

import httpx

from api.models import GenerateRequest
from api.prompt_builder import PromptBuilder
from api.validator import LuaValidator

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

OLLAMA_OPTIONS: dict = {
    "num_ctx": 4096,
    "num_predict": 512,
    "temperature": 0.1,
    "seed": 42,
}


class AsyncOllamaClient:
    """Async HTTP client for Ollama /api/generate (non-streaming API, but async network I/O)."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": OLLAMA_OPTIONS,
        }
        logger.debug("POST %s model=%s prompt_len=%d", url, self.model, len(prompt))

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=120.0)
            response.raise_for_status()
            return response.json().get("response", "")


def _parse_llm_response(raw: str) -> tuple[str, str]:
    """
    Extract conversational message and Lua code from the LLM response.
    Returns: (message, code)
    """
    code = ""
    message = ""

    # Priority 1: Parse <code>...</code> tag
    code_tag = re.search(r"<code>(.*?)</code>", raw, re.DOTALL | re.IGNORECASE)
    if code_tag:
        code = code_tag.group(1).strip()
        # Extract message by removing the code block
        message = re.sub(r"<code>.*?</code>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
        # Clean up <thinking> tags from the message
        message = re.sub(r"</?thinking>", "", message, flags=re.IGNORECASE).strip()
        return message, code

    # Priority 2: Markdown fences ```lua ... ```
    fenced = re.search(r"```(?:lua)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fenced:
        code = fenced.group(1).strip()
        message = re.sub(r"```(?:lua)?\s*\n?.*?\n?```", "", raw, flags=re.DOTALL).strip()
        return message, code

    # Priority 3: No code tags found. Might be a pure conversational response (Clarification).
    return raw.strip(), ""


class AgentPipeline:
    """
    Оркестратор полного цикла: генерация → валидация → исправление.
    Теперь работает как асинхронный генератор, отдающий (yield) статусы для SSE.
    """

    def __init__(
            self,
            ollama_client: AsyncOllamaClient | None = None,
            prompt_builder: PromptBuilder | None = None,
            validator: LuaValidator | None = None,
    ) -> None:
        self.ollama = ollama_client or AsyncOllamaClient()
        self.builder = prompt_builder or PromptBuilder()
        self.validator = validator or LuaValidator()

    async def generate_stream(self, request: GenerateRequest):
        """
        Async generator yielding dicts representing TaskStatusEvent.
        """
        error_context: str | None = None
        best_code: str = ""
        last_error: str = ""

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("Attempt %d/%d | prompt=%r", attempt, MAX_RETRIES, request.prompt[:60])

            yield {"stage": "generating", "message": f"Попытка {attempt} из {MAX_RETRIES}...", "code": best_code, "error": ""}

            # 1. Build Prompt
            prompt = self.builder.build(
                prompt=request.prompt,
                context=request.context,
                error_context=error_context,
            )

            # 2. Call Ollama (Async)
            try:
                raw_response = await self.ollama.generate(prompt)
            except httpx.HTTPError as exc:
                logger.error("Ollama HTTP error attempt %d: %s", attempt, exc)
                error_context = f"HTTP error: {exc}"
                last_error = error_context
                yield {"stage": "retrying", "message": "Сетевая ошибка Ollama", "code": best_code, "error": last_error}
                await asyncio.sleep(1) # Backoff
                continue

            # 3. Extract Message & Code
            message, code = _parse_llm_response(raw_response)

            # Check for Clarification Loop (no code produced)
            if not code:
                logger.info("No code detected. Treating as Clarification Loop.")
                yield {"stage": "done", "message": message, "code": "", "error": ""}
                return

            if not best_code:
                best_code = code

            # 4. Validate Code (Run sync validation in a threadpool so we don't block the event loop)
            yield {"stage": "validating", "message": "Проверка синтаксиса (luac)...", "code": code, "error": ""}

            is_valid, lua_error = await asyncio.to_thread(self.validator.validate, code)

            # 5. Handle Validation Result
            if is_valid:
                logger.info("Valid Lua on attempt %d.", attempt)
                yield {"stage": "done", "message": message, "code": code, "error": ""}
                return

            # 6. Retry Logic
            logger.warning("Attempt %d invalid syntax: %s", attempt, lua_error)
            best_code = code
            error_context = lua_error
            last_error = lua_error

            if attempt < MAX_RETRIES:
                yield {"stage": "retrying", "message": "Найдена ошибка синтаксиса, исправляю...", "code": code, "error": lua_error}

        # 7. Max Retries Exhausted
        logger.error("All %d attempts failed. Returning best attempt.", MAX_RETRIES)
        yield {"stage": "error", "message": "Не удалось сгенерировать валидный код за отведенное число попыток.", "code": best_code, "error": last_error}

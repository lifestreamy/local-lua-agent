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

# Configurable Context & Prediction Limits
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "3072"))
OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))

OLLAMA_OPTIONS: dict = {
    "num_ctx": OLLAMA_NUM_CTX,
    "num_predict": OLLAMA_NUM_PREDICT,
    "temperature": 0.4,
}

class AsyncOllamaClient:
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
    code = ""
    message = ""

    code_tag = re.search(r"<code>(.*?)</code>", raw, re.DOTALL | re.IGNORECASE)
    if code_tag:
        code = code_tag.group(1).strip()
        message = re.sub(r"<code>.*?</code>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
        message = re.sub(r"</?thinking>", "", message, flags=re.IGNORECASE).strip()
        return message, code

    fenced = re.search(r"```(?:lua)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fenced:
        code = fenced.group(1).strip()
        message = re.sub(r"```(?:lua)?\s*\n?.*?\n?```", "", raw, flags=re.DOTALL).strip()
        return message, code

    return raw.strip(), ""

def _truncate_context_for_agent(context: str, max_chars: int = 2500) -> str:
    """Hard cap the context window to strictly fit inside num_ctx with room to spare."""
    if not context or len(context) <= max_chars:
        return context

    truncated = context[-max_chars:]
    user_idx = truncated.find("User:")
    if user_idx != -1:
        return truncated[user_idx:]
    return truncated

class AgentPipeline:
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
        error_context: str | None = None
        best_code: str = ""
        last_error: str = ""

        # SERVER-SIDE CONTEXT HARD CAP (2500 chars)
        safe_context = _truncate_context_for_agent(request.context, max_chars=2500)

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("Attempt %d/%d | prompt=%r", attempt, MAX_RETRIES, request.prompt[:60])

            yield {"stage": "generating", "message": f"Попытка {attempt} из {MAX_RETRIES}...", "code": best_code, "error": ""}

            prompt = self.builder.build(
                prompt=request.prompt,
                context=safe_context,
                error_context=error_context,
            )

            try:
                raw_response = await self.ollama.generate(prompt)
            except httpx.HTTPError as exc:
                logger.error("Ollama HTTP error attempt %d: %s", attempt, exc)
                error_context = f"HTTP error: {exc}"
                last_error = error_context
                yield {"stage": "retrying", "message": "Сетевая ошибка Ollama", "code": best_code, "error": last_error}
                await asyncio.sleep(1)
                continue

            message, code = _parse_llm_response(raw_response)

            if not code:
                logger.info("No code detected. Treating as Clarification Loop.")
                yield {"stage": "done", "message": message, "code": "", "error": ""}
                return

            if not best_code:
                best_code = code

            yield {"stage": "validating", "message": "Проверка синтаксиса (luac)...", "code": code, "error": ""}

            is_valid, lua_error = await asyncio.to_thread(self.validator.validate, code)

            if is_valid:
                logger.info("Valid Lua on attempt %d.", attempt)
                yield {"stage": "done", "message": message, "code": code, "error": ""}
                return

            logger.warning("Attempt %d invalid syntax: %s", attempt, lua_error)
            best_code = code
            error_context = lua_error
            last_error = lua_error

            if attempt < MAX_RETRIES:
                yield {"stage": "retrying", "message": "Найдена ошибка синтаксиса, исправляю...", "code": code, "error": lua_error}

        logger.error("All %d attempts failed. Returning best attempt.", MAX_RETRIES)
        yield {"stage": "error", "message": "Не удалось сгенерировать валидный код за отведенное число попыток.", "code": best_code, "error": last_error}
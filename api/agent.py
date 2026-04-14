"""
api/agent.py — Ollama client and AgentPipeline.

Pipeline steps:
1. Build prompt (system_prompt + optional context + user task).
2. POST to Ollama /api/generate.
3. Extract Lua from <code>...</code> section of the response.
4. Validate with luac.
5. If invalid and retries remain → rebuild prompt with error context, go to 2.
6. After MAX_RETRIES failures → return best attempt.

Response format expected from LLM:
<thinking>
  ...reasoning...
</thinking>
<code>
  ...raw lua code...
</code>
"""

import logging
import os
import re

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
    "temperature": 0.1, # если условия требуют точное совпадение, поставить 0.0
    "seed": 42, # для воспроизводимости (температура 0 + seed = максимальный детерминизм)
}


class OllamaClient:
    """Thin HTTP client for Ollama /api/generate (non-streaming)."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": OLLAMA_OPTIONS,
        }
        logger.debug("POST %s model=%s prompt_len=%d", url, self.model, len(prompt))
        response = httpx.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json().get("response", "")


def _extract_lua_code(raw: str) -> str:
    """
    Extract Lua code from the LLM response.

    Priority:
    1. Parse <code>...</code> tag (our primary CoT format).
    2. Strip markdown fences ```lua...``` as fallback (model disobedience).
    3. Return the entire raw string stripped as last resort.
    """
    # Primary: <code>...</code>
    code_tag = re.search(r"<code>(.*?)</code>", raw, re.DOTALL | re.IGNORECASE)
    if code_tag:
        return code_tag.group(1).strip()

    # Fallback 1: ```lua ... ``` or ``` ... ```
    fenced = re.search(r"```(?:lua)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # Fallback 2: raw string (model ignored all formatting)
    return raw.strip()


class AgentPipeline:
    """
    Оркестратор полного цикла: генерация → валидация → исправление.

    Принимает GenerateRequest с полями prompt и опциональным context.
    Передаёт оба поля в PromptBuilder, который формирует финальный промпт.
    Повторяет попытки до MAX_RETRIES, передавая ошибку luac обратно в модель.
    """

    def __init__(
            self,
            ollama_client: OllamaClient | None = None,
            prompt_builder: PromptBuilder | None = None,
            validator: LuaValidator | None = None,
    ) -> None:
        self.ollama = ollama_client or OllamaClient()
        self.builder = prompt_builder or PromptBuilder()
        self.validator = validator or LuaValidator()

    def generate(self, request: GenerateRequest) -> str:
        """
        Генерирует валидный Lua-код по запросу пользователя.

        Аргументы:
            request: Pydantic-модель с полями:
                     - prompt  (обязательно) — текст задачи на естественном языке
                     - context (опционально) — существующий Lua-код для доработки

        Возвращает:
            Строку Lua-кода — либо синтаксически валидную, либо лучший вариант
            из всех попыток, если ни одна не прошла валидацию.
        """
        error_context: str | None = None
        best_code: str = ""

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(
                "Attempt %d/%d | prompt=%r | has_context=%s",
                attempt, MAX_RETRIES,
                request.prompt[:60],
                bool(request.context),
            )

            prompt = self.builder.build(
                prompt=request.prompt,
                context=request.context,
                error_context=error_context,
            )

            try:
                raw_response = self.ollama.generate(prompt)
            except httpx.HTTPError as exc:
                logger.error("Ollama HTTP error attempt %d: %s", attempt, exc)
                error_context = f"HTTP error: {exc}"
                continue

            code = _extract_lua_code(raw_response)

            if not best_code:
                best_code = code

            is_valid, lua_error = self.validator.validate(code)

            if is_valid:
                logger.info("Valid Lua on attempt %d.", attempt)
                return code

            logger.warning("Attempt %d invalid syntax: %s", attempt, lua_error)
            best_code = code
            error_context = lua_error

        logger.error("All %d attempts failed. Returning best attempt.", MAX_RETRIES)
        return best_code
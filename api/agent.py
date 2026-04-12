"""
api/agent.py — AgentPipeline: orchestrates OllamaClient, PromptBuilder, LuaValidator.

Model warm-up is handled by main.py at startup (lifespan event).
This module focuses only on generation + validation + retry loop.
"""

import logging
import os
import re
import time

import httpx

from api.prompt_builder import PromptBuilder
from api.validator import LuaValidator

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

OLLAMA_OPTIONS: dict = {
    "num_ctx": 4096,
    "num_predict": 512,
    "temperature": 0.1,
}


class OllamaClient:
    """Thin HTTP client for Ollama /api/generate (non-streaming)."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def warm_up(self, max_wait: int = 60) -> None:
        """
        Block until Ollama has the model loaded in VRAM.
        Called ONCE at startup by main.py lifespan — NOT per request.

        Polls /api/generate with a 1-token request every 3 seconds.
        Gives up after max_wait seconds and logs a warning.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": "hi",
            "stream": False,
            "options": {"num_ctx": 512, "num_predict": 1},
        }
        deadline = time.time() + max_wait
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                logger.info("Warm-up ping %d (waiting for model to load into VRAM)...", attempt)
                r = httpx.post(url, json=payload, timeout=30.0)
                if r.status_code == 200:
                    logger.info("Ollama model loaded successfully after %d ping(s).", attempt)
                    return
                logger.warning("Ping %d: Ollama returned %d, retrying in 3s...", attempt, r.status_code)
            except httpx.HTTPError as exc:
                logger.warning("Ping %d: connection error (%s), retrying in 3s...", attempt, exc)
            time.sleep(3)
        logger.warning(
            "Warm-up gave up after %ds. Model may not be loaded. "
            "First real request will trigger load (may be slow).", max_wait
        )

    def generate(self, prompt: str) -> str:
        """
        Send prompt to Ollama and return raw response text.
        Model is expected to already be in VRAM (warm_up called at startup).
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": OLLAMA_OPTIONS,
        }
        logger.debug("POST %s prompt_len=%d", url, len(prompt))
        response = httpx.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json().get("response", "")


def _extract_lua_code(raw: str) -> str:
    """
    Extract Lua code from the LLM response.
    Priority: <code>...</code> → markdown fences → raw string.
    """
    code_tag = re.search(r"<code>(.*?)</code>", raw, re.DOTALL | re.IGNORECASE)
    if code_tag:
        return code_tag.group(1).strip()
    fenced = re.search(r"```(?:lua)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return raw.strip()


class AgentPipeline:
    """Orchestrates the full generate → validate → fix loop."""

    def __init__(
            self,
            ollama_client: OllamaClient | None = None,
            prompt_builder: PromptBuilder | None = None,
            validator: LuaValidator | None = None,
    ) -> None:
        self.ollama = ollama_client or OllamaClient()
        self.builder = prompt_builder or PromptBuilder()
        self.validator = validator or LuaValidator()

    def generate(self, user_query: str) -> str:
        """
        Generate valid Lua code for the given natural language query.
        Returns best Lua code string within MAX_RETRIES attempts.
        """
        error_context: str | None = None
        best_code: str = ""

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("Attempt %d/%d | query=%r", attempt, MAX_RETRIES, user_query[:60])
            prompt = self.builder.build(user_query, error_context=error_context)

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

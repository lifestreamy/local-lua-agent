"""
api/prompt_builder.py — Assembles the full prompt string for Ollama.

Reads system_prompt.txt once at import time (cached).
On each call, appends the user query and optionally:
  - context   (existing Lua code the user wants to modify)
  - error_ctx (luac error from the previous attempt for fix iterations)
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


def _load_system_prompt() -> str:
    try:
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("system_prompt.txt not found at %s", _SYSTEM_PROMPT_PATH)
        return ""


_SYSTEM_PROMPT: str = _load_system_prompt()


class PromptBuilder:
    """Строит финальную строку промпта для отправки в Ollama /api/generate."""

    def build(
            self,
            prompt: str,
            context: str | None = None,
            error_context: str | None = None,
    ) -> str:
        """
        Собирает финальный промпт из системного шаблона, опционального контекста и задачи.

        Аргументы:
            prompt:        Текстовый запрос пользователя на естественном языке.
            context:       Существующий Lua-код для доработки (опционально).
                           Если передан — вставляется в промпт как блок EXISTING CODE TO MODIFY.
            error_context: Ошибка luac из предыдущей попытки (для retry-цикла).
                           Если передан — модель видит что сломалось и пытается исправить.

        Возвращает:
            Готовую строку промпта для отправки в Ollama.
        """
        parts: list[str] = [_SYSTEM_PROMPT.strip(), ""]

        # Вставляем блок с существующим кодом, если пользователь хочет доработать его
        if context and context.strip():
            parts.append(
                f"EXISTING CODE TO MODIFY:\n```lua\n{context.strip()}\n```"
            )
            parts.append("")

        # При retry — показываем модели ошибку прошлой попытки
        if error_context:
            parts.append(
                f"## Previous attempt failed\n"
                f"The Lua code you generated had the following syntax error:\n"
                f"{error_context}\n"
                f"Fix the error and output corrected Lua code only.\n"
            )

        parts.append(f"User: {prompt.strip()}")
        parts.append("Code:")

        return "\n".join(parts)
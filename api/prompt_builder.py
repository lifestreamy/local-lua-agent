"""
api/prompt_builder.py — Assembles the full prompt string for Ollama.

Reads system_prompt.txt once at import time (cached).
On each call, appends the user query and optionally a previous error context
so the model knows what went wrong and can fix it.
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
    """Builds the full prompt string to send to the Ollama /api/generate endpoint."""

    def build(self, user_query: str, error_context: str | None = None) -> str:
        """
        Assemble the full prompt.

        Args:
            user_query:    The natural language task from the user.
            error_context: luac error from the previous attempt (fix iteration).
                           If None, this is the first attempt.

        Returns:
            Full prompt string ready to send to Ollama.
        """
        parts: list[str] = [_SYSTEM_PROMPT.strip(), ""]

        if error_context:
            parts.append(
                f"## Previous attempt failed\n"
                f"The Lua code you generated had the following syntax error:\n"
                f"{error_context}\n"
                f"Fix the error and output corrected Lua code only.\n"
            )

        parts.append(f"User: {user_query.strip()}")
        parts.append("Code:")

        return "\n".join(parts)

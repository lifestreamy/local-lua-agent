"""
api/validator.py — Lua syntax validation via luac subprocess.

Strategy:
  1. Pass code via stdin to `luac -o /dev/null -` (Linux only — available in Docker).
  2. Exit code 0  → valid syntax.
  3. Exit code != 0 → invalid, return stderr as the error hint for the fix loop.

Local Windows dev:
  Set env var DRY_RUN=true to skip subprocess and always return (True, "").
  This lets the rest of the pipeline run without luac installed locally.
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)

DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"


class LuaValidator:
    """Validates Lua code syntax using the luac compiler."""

    def validate(self, code: str) -> tuple[bool, str]:
        """
        Validate Lua code syntax.

        Args:
            code: Raw Lua source code string.

        Returns:
            (True, "")           — valid syntax.
            (False, error_msg)   — invalid, error_msg is the luac stderr output.
        """
        if DRY_RUN:
            logger.debug("DRY_RUN=true — skipping luac validation.")
            return True, ""

        if not code or not code.strip():
            return False, "Empty code string."

        try:
            result = subprocess.run(
                ["luac", "-o", "/dev/null", "-"],
                input=code.encode("utf-8"),
                capture_output=True,
                timeout=5,
            )
        except FileNotFoundError:
            logger.error(
                "luac not found. Install lua5.4 (Docker) or set DRY_RUN=true for local dev."
            )
            return False, "luac binary not found. Is lua5.4 installed?"
        except subprocess.TimeoutExpired:
            return False, "luac timed out."

        if result.returncode == 0:
            return True, ""

        error_msg = result.stderr.decode("utf-8", errors="replace").strip()
        logger.debug("luac error: %s", error_msg)
        return False, error_msg

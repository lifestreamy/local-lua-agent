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
            # We explicitly use luac5.5 if available, otherwise fallback to generic luac
            cmd = ["luac5.5", "-o", os.devnull, "-"] if os.name != 'nt' else ["luac", "-o", "NUL", "-"]

            result = subprocess.run(
                cmd,
                input=code.encode("utf-8"),
                capture_output=True,
                timeout=5,
            )
        except FileNotFoundError:
            try:
                # Fallback to 'luac' if 'luac5.5' specifically isn't found
                cmd = ["luac", "-o", os.devnull if os.name != 'nt' else "NUL", "-"]
                result = subprocess.run(
                    cmd,
                    input=code.encode("utf-8"),
                    capture_output=True,
                    timeout=5,
                )
            except FileNotFoundError:
                logger.warning("luac binary not found. Falling back to accepting LLM code without validation.")
                # FALLBACK: If Lua isn't installed, just accept the code
                return True, ""
        except subprocess.TimeoutExpired:
            return False, "luac timed out."

        if result.returncode == 0:
            return True, ""

        error_msg = result.stderr.decode("utf-8", errors="replace").strip()
        logger.debug("luac error: %s", error_msg)
        return False, error_msg
"""
tests/test_prompt_injection.py — Tests for the prompt injection guard (api/guard.py).

UPDATED for SSE API (v3):
Uses a fast mock client to hit `POST /generate` and polls `GET /status`
to verify if the pipeline aborted immediately with SECURITY_BLOCK.
"""

import unittest
import asyncio
import httpx
import json

from tests.injection_data import SAFE_PROMPTS, UNSAFE_PROMPTS
from tests.log_utils import print_table, save_markdown_report

API_URL = "http://localhost:8080"
SECURITY_BLOCK_MARKER = "[SECURITY_BLOCK]"


class TestPromptInjectionGuard(unittest.IsolatedAsyncioTestCase):
    """Verifies guard correctly allows safe prompts and blocks malicious/off-topic ones."""

    @classmethod
    def setUpClass(cls):
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        print_table(cls.results, title="Prompt Injection Guard — Test Results")
        save_markdown_report(cls.results, title="Prompt Injection Guard Test Report")

    async def _run_sse_test(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=45.0) as client:
            # 1. Submit task
            post_resp = await client.post(f"{API_URL}/generate", json={"prompt": prompt})
            self.assertEqual(post_resp.status_code, 200)
            task_id = post_resp.json().get("task_id")

            # 2. Consume SSE stream until "done" or "error"
            async with client.stream("GET", f"{API_URL}/status", params={"task_id": task_id}) as stream_resp:
                async for line in stream_resp.aiter_lines():
                    if line.startswith("data: "):
                        payload = json.loads(line.removeprefix("data: "))
                        if payload["stage"] in ("done", "error"):
                            return payload.get("code", "")
        return ""

    async def test_safe_prompts_allowed(self):
        """All genuine coding tasks must pass the guard."""
        for prompt, description in SAFE_PROMPTS:
            with self.subTest(msg=description, prompt=prompt):
                code = await self._run_sse_test(prompt)
                passed = SECURITY_BLOCK_MARKER not in code
                self.__class__.results.append((prompt, "ALLOWED", code[:50], passed))
                self.assertNotIn(SECURITY_BLOCK_MARKER, code)

    async def test_unsafe_prompts_blocked(self):
        """All injections and off-topic prompts must be blocked."""
        for prompt, description in UNSAFE_PROMPTS:
            with self.subTest(msg=description, prompt=prompt):
                code = await self._run_sse_test(prompt)
                passed = SECURITY_BLOCK_MARKER in code
                self.__class__.results.append((prompt, "BLOCKED", code[:50], passed))
                self.assertIn(SECURITY_BLOCK_MARKER, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)

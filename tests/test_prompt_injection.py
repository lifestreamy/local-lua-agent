"""
tests/test_prompt_injection.py — Tests for the prompt injection guard (api/guard.py).

Requires:
    - Uvicorn running: uvicorn api.main:app --host 0.0.0.0 --port 8080
    - Ollama running with the model loaded

Run:
    python -m unittest tests.test_prompt_injection -v
"""

import unittest
import httpx

from tests.injection_data import SAFE_PROMPTS, UNSAFE_PROMPTS
from tests.log_utils import print_table, save_markdown_report

API_URL = "http://localhost:8080/generate"
SECURITY_BLOCK_MARKER = "[SECURITY_BLOCK]"


class TestPromptInjectionGuard(unittest.TestCase):
    """Verifies guard correctly allows safe prompts and blocks malicious/off-topic ones."""

    @classmethod
    def setUpClass(cls):
        cls.client = httpx.Client(timeout=45.0)
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        print_table(cls.results, title="Prompt Injection Guard — Test Results")
        save_markdown_report(cls.results, title="Prompt Injection Guard Test Report")

    def _post(self, prompt: str) -> str:
        response = self.client.post(API_URL, json={"prompt": prompt})
        self.assertEqual(response.status_code, 200, f"API non-200 for: {prompt}")
        return response.json().get("code", "")

    def test_safe_prompts_allowed(self):
        """All genuine coding tasks must pass the guard."""
        for prompt, description in SAFE_PROMPTS:
            with self.subTest(msg=description, prompt=prompt):
                code = self._post(prompt)
                passed = SECURITY_BLOCK_MARKER not in code and len(code.strip()) > 0
                self.__class__.results.append(
                    (prompt, "ALLOWED", code, passed)
                )
                self.assertNotIn(
                    SECURITY_BLOCK_MARKER, code,
                    f"Guard incorrectly blocked safe prompt: {prompt!r}\nGot: {code!r}"
                )

    def test_unsafe_prompts_blocked(self):
        """All injections and off-topic prompts must be blocked."""
        for prompt, description in UNSAFE_PROMPTS:
            with self.subTest(msg=description, prompt=prompt):
                code = self._post(prompt)
                passed = SECURITY_BLOCK_MARKER in code
                self.__class__.results.append(
                    (prompt, "BLOCKED", code, passed)
                )
                self.assertIn(
                    SECURITY_BLOCK_MARKER, code,
                    f"Guard failed to block unsafe prompt: {prompt!r}\nGot: {code!r}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

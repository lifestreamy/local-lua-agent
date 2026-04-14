"""
tests/test_request.py — Raw Ollama smoke test (bypasses FastAPI).

Hits Ollama directly on port 11434 to verify the model is loaded
and responding. Useful for diagnosing if failures are in your API
layer vs Ollama itself.

Note: this test does NOT go through /generate or the guard.
      For full API tests, see test_base_cases.py.
"""

import unittest
import httpx


class TestRawOllamaRequest(unittest.TestCase):

    def test_ollama_responds(self):
        payload = {
            "model": "qwen2.5-coder:7b-instruct-q4_K_M",
            "prompt": "hello",
            "stream": False,
            "keep_alive": -1,
        }
        r = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json=payload,
            timeout=30.0,
        )
        print(r.status_code)
        print(r.text[:500])
        self.assertEqual(r.status_code, 200, "Ollama did not return 200")
        self.assertNotIn("502", r.text[:100], "Got 502 proxy error from Ollama")
        self.assertIn("response", r.json(), "Response JSON missing 'response' key")


if __name__ == "__main__":
    unittest.main()
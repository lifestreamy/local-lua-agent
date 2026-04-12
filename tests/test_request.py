import unittest
import httpx


class MyTestCase(unittest.TestCase):
    def test_something(self):
        payload = {
            "model": "qwen2.5-coder:7b-instruct-q4_K_M",
            "prompt": "hello",
            "stream": False,
            "keep_alive": -1,
        }
        r = httpx.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=30.0)
        print(r.status_code)
        print(r.text[:500])
        self.assertNotEqual(r.text[:500], "502")


if __name__ == '__main__':
    unittest.main()

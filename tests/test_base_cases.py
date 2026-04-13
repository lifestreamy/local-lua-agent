"""
tests/test_base_cases.py — End-to-end accuracy tests for the /generate endpoint.

Each test case sends multiple rephrasings of the same intent and checks
that the returned Lua code matches the canonical expected output.

Uses log_utils for all reporting (stdout table + Markdown artifact).
"""

import time
import unittest
import httpx

from tests.log_utils import print_table, save_markdown_report, Row
from tests.test_base_cases_data import TEST_CASES

API_URL = "http://localhost:8080/generate"


def clean_lua(code: str) -> str:
    """Normalise whitespace for stable string comparison."""
    if not code:
        return ""
    return "\n".join(line.strip() for line in code.strip().splitlines() if line.strip())


class TestBaseCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            resp = httpx.get("http://localhost:8080/health", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"Health returned {resp.status_code}")
        except Exception as e:
            raise unittest.SkipTest(f"FastAPI server not ready on localhost:8080 — {e}")

        cls._all_rows: list[Row] = []

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "_all_rows") or not cls._all_rows:
            return
        print_table(cls._all_rows, title="Base Cases — Full Run")
        save_markdown_report(cls._all_rows, title="Base Cases Report")

    # ------------------------------------------------------------------
    # Internal runner
    # ------------------------------------------------------------------

    def _run_case(self, case_id: str) -> None:
        data = TEST_CASES[case_id]
        expected_lua = clean_lua(data["expected"])
        prompts: list[str] = data["prompts"]

        print(f"\n>>> {case_id} ({len(prompts)} prompts)", flush=True)

        for i, prompt in enumerate(prompts, 1):
            with self.subTest(prompt=prompt):
                t0 = time.time()
                actual_lua = ""
                try:
                    resp = httpx.post(
                        API_URL,
                        json={"prompt": prompt},
                        timeout=60.0,
                    )
                    if resp.status_code == 200:
                        actual_lua = resp.json().get("code", "")
                    else:
                        actual_lua = f"HTTP {resp.status_code}"
                except Exception as exc:
                    actual_lua = f"Error: {exc}"

                elapsed = (time.time() - t0) * 1000
                actual_clean = clean_lua(actual_lua)
                passed = actual_clean == expected_lua

                row: Row = (prompt, expected_lua[:60], actual_clean[:80], passed)
                self.__class__._all_rows.append(row)

                status = "PASS" if passed else "FAIL"
                print(
                    f"  [{i}/{len(prompts)}] {status} ({elapsed:.0f}ms)\n"
                    f"    prompt:   {prompt!r}\n"
                    f"    expected: {expected_lua!r}\n"
                    f"    actual:   {actual_clean!r}",
                    flush=True,
                )

                self.assertEqual(
                    actual_clean,
                    expected_lua,
                    f"Mismatch on prompt: {prompt!r}",
                )

    # ------------------------------------------------------------------
    # Test methods — one per case in TEST_CASES
    # ------------------------------------------------------------------

    def test_get_last_email(self):         self._run_case("test_get_last_email")
    def test_increment_counter(self):      self._run_case("test_increment_counter")
    def test_create_empty_array(self):     self._run_case("test_create_empty_array")
    def test_filter_done_orders(self):     self._run_case("test_filter_done_orders")
    def test_sum_numbers(self):            self._run_case("test_sum_numbers")
    def test_check_is_admin(self):         self._run_case("test_check_is_admin")
    def test_find_max_number(self):        self._run_case("test_find_max_number")
    def test_count_elements(self):         self._run_case("test_count_elements")
    def test_get_first_element(self):      self._run_case("test_get_first_element")
    def test_check_array_empty(self):      self._run_case("test_check_array_empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
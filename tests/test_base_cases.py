import time
import unittest
import httpx
import os
import json
from datetime import datetime
from tests.test_base_cases_data import TEST_CASES

API_URL = "http://localhost:8080/generate"
# Standard practice: create a separate reports directory inside tests/
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def clean_lua(code: str) -> str:
    """Removes extra whitespace and normalizes newlines for stable comparison."""
    if code is None:
        return ""
    return "\n".join(line.strip() for line in code.strip().splitlines() if line.strip())


class TestBaseCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            httpx.get("http://localhost:8080/health", timeout=5.0)
        except Exception:
            raise unittest.SkipTest("FastAPI server is not running on localhost:8080")

        # Initialize tracking variables for the summary
        cls.run_summary = {}
        cls.failure_details = []
        cls.start_time = datetime.now()

    @classmethod
    def tearDownClass(cls):
        # Prevent errors if setUpClass failed
        if not hasattr(cls, 'run_summary'):
            return

        end_time = datetime.now()
        duration = (end_time - cls.start_time).total_seconds()

        # Build the Markdown Report
        md_lines = [
            "# Test Run Report",
            f"**Date:** {cls.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {duration:.2f} seconds",
            "",
            "## Summary Table",
            "",
            "| Test Case | Total | Passed | Failed | Accuracy |",
            "|-----------|-------|--------|--------|----------|"
        ]

        total_prompts = 0
        total_passed = 0

        for case_id, stats in cls.run_summary.items():
            t = stats["total"]
            p = stats["passed"]
            f = stats["failed"]
            acc = (p / t * 100) if t > 0 else 0
            md_lines.append(f"| {case_id} | {t} | {p} | {f} | {acc:.1f}% |")

            total_prompts += t
            total_passed += p

        overall_acc = (total_passed / total_prompts * 100) if total_prompts > 0 else 0
        md_lines.append(
            f"| **TOTAL** | **{total_prompts}** | **{total_passed}** | **{total_prompts - total_passed}** | **{overall_acc:.1f}%** |")
        md_lines.append("")

        # Append Failure Details
        if cls.failure_details:
            md_lines.append("## Failure Details")
            for idx, fail in enumerate(cls.failure_details, 1):
                md_lines.append(f"### {idx}. {fail['case_id']}")
                md_lines.append(f"**Prompt:** `{fail['prompt']}`")
                md_lines.append(f"**Expected:**\n```lua\n{fail['expected']}\n```")
                md_lines.append(f"**Actual:**\n```lua\n{fail['actual']}\n```")
                md_lines.append(f"**Error:** {fail.get('error', 'Mismatch')}\n")
        else:
            md_lines.append("## Failure Details\n\nNo failures! 🎉\n")

        md_content = "\n".join(md_lines)

        # Print the beautiful table to console
        print("\n" + "=" * 60)
        print(md_content)
        print("=" * 60 + "\n")

        # Save artifacts to the reports folder
        timestamp_str = cls.start_time.strftime("%Y%m%d_%H%M%S")
        md_path = os.path.join(REPORTS_DIR, f"report_{timestamp_str}.md")
        json_path = os.path.join(REPORTS_DIR, f"report_{timestamp_str}.json")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        json_data = {
            "timestamp": cls.start_time.isoformat(),
            "duration_seconds": duration,
            "summary": cls.run_summary,
            "overall_accuracy": overall_acc,
            "failures": cls.failure_details
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"Reports saved to:\n- {md_path}\n- {json_path}")

    def run_case(self, case_id: str):
        data = TEST_CASES[case_id]
        expected_lua = data["expected"]
        prompts = data["prompts"]
        expected_clean = clean_lua(expected_lua)

        # Initialize tracking for this specific test case
        self.__class__.run_summary[case_id] = {"total": len(prompts), "passed": 0, "failed": 0}

        print(f"\n=== Starting {case_id} ===", flush=True)

        for i, prompt in enumerate(prompts, 1):
            with self.subTest(prompt=prompt):
                start_time = time.time()
                error_msg = None
                try:
                    response = httpx.post(API_URL, json={"prompt": prompt}, timeout=60.0)
                    status_code = response.status_code
                    actual_lua = response.json().get("code", "") if status_code == 200 else f"HTTP {status_code}"
                except Exception as e:
                    actual_lua = f"Error: {str(e)}"
                    status_code = 500
                    error_msg = str(e)

                elapsed_ms = (time.time() - start_time) * 1000
                actual_clean = clean_lua(actual_lua)

                passed = (actual_clean == expected_clean) and (status_code == 200)
                res_str = "PASS" if passed else "FAIL"

                if passed:
                    self.__class__.run_summary[case_id]["passed"] += 1
                else:
                    self.__class__.run_summary[case_id]["failed"] += 1
                    self.__class__.failure_details.append({
                        "case_id": case_id,
                        "prompt": prompt,
                        "expected": expected_clean,
                        "actual": actual_clean,
                        "error": error_msg or "Semantics / String Mismatch"
                    })

                print(f"  [{i}/{len(prompts)}] Prompt: {prompt}")
                print(f"  Expected: {expected_clean!r}")
                print(f"  Actual:   {actual_clean!r}")
                print(f"  Result:   {res_str} | Took: {elapsed_ms:.2f} ms\n", flush=True)

                self.assertEqual(actual_clean, expected_clean, f"Failed on prompt: '{prompt}'")

    def test_get_last_email(self):
        self.run_case("test_get_last_email")

    def test_increment_counter(self):
        self.run_case("test_increment_counter")

    def test_create_empty_array(self):
        self.run_case("test_create_empty_array")

    def test_filter_done_orders(self):
        self.run_case("test_filter_done_orders")

    def test_sum_numbers(self):
        self.run_case("test_sum_numbers")

    def test_check_is_admin(self):
        self.run_case("test_check_is_admin")

    def test_find_max_number(self):
        self.run_case("test_find_max_number")

    def test_count_elements(self):
        self.run_case("test_count_elements")

    def test_get_first_element(self):
        self.run_case("test_get_first_element")

    def test_check_array_empty(self):
        self.run_case("test_check_array_empty")


if __name__ == '__main__':
    unittest.main()

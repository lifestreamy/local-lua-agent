import asyncio
import json
import httpx
import sys
import os
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from tests.log_utils import save_markdown_report
from tests.session_stress_data import STRESS_TEST_PROMPTS

BASE_URL = "http://localhost:8080"
CONTEXT_LIMIT = 4096

def print_timed_table(rows, title="Test Results"):
    col_widths = [
        max(len("Prompt"), max((len(r[0][:50]) for r in rows), default=0)),
        max(len("Expected"), max((len(r[1]) for r in rows), default=0)),
        max(len("Actual (truncated)"), max((len(r[2][:40]) for r in rows), default=0)),
        4, # Pass
        10 # Time
    ]

    def row_line(cols):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, col_widths)) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    print(f"\\n{'=' * 90}")
    print(f"  {title}")
    print(f"{'=' * 90}")
    print(sep)
    print(row_line(["Prompt", "Expected", "Actual (truncated)", "Pass", "Time (s)"]))
    print(sep)
    for prompt, expected, actual, passed, duration in rows:
        p = "✅" if passed else "❌"
        t = f"{duration:.2f}s"
        print(row_line([prompt[:50], expected, actual[:40], p, t]))
    print(sep)
    passed_count = sum(1 for r in rows if r[3])
    print(f"\\n  Result: {passed_count}/{len(rows)} passed")
    print(f"{'=' * 90}\\n")

async def run_stress_test():
    print("=====================================================")
    print(f" LONG SESSION STRESS TEST ({len(STRESS_TEST_PROMPTS)} TURNS) WITH TIMERS")
    print("=====================================================\\n")

    history = ""
    results = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, prompt in enumerate(STRESS_TEST_PROMPTS, start=1):
            print(f"[TURN {i:02d}/{len(STRESS_TEST_PROMPTS)}] Prompt: '{prompt[:50]}...'")

            payload = {"prompt": prompt, "context": history}

            start_time = time.perf_counter()

            try:
                resp = await client.post(f"{BASE_URL}/generate", json=payload)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]

                current_code = ""
                current_msg = ""
                is_blocked = False

                async with client.stream("GET", f"{BASE_URL}/status?task_id={task_id}") as stream:
                    async for line in stream.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if "[SECURITY_BLOCK]" in data.get("code", ""):
                                is_blocked = True
                            if data.get("stage") == "done":
                                current_code = data.get("code", "")
                                current_msg = data.get("message", "")
                                break

                end_time = time.perf_counter()
                duration = end_time - start_time

                if is_blocked:
                    print(f"  ❌ BLOCKED! Time: {duration:.2f}s")
                    results.append((prompt, "ALLOWED", "[SECURITY_BLOCK]", False, duration))
                else:
                    print(f"  ✅ SUCCESS! Time: {duration:.2f}s")
                    actual_trunc = current_code.replace("\\n", " ") if current_code else current_msg.replace("\\n", " ")
                    results.append((prompt, "ALLOWED", actual_trunc, True, duration))

                    new_turn = f"User: {prompt}\\n"
                    if current_msg:
                        new_turn += f"Assistant: {current_msg}\\n"
                    if current_code:
                        new_turn += f"```lua\\n{current_code}\\n```\\n"

                    history += new_turn

                    if len(history) > CONTEXT_LIMIT:
                        truncated = history[-CONTEXT_LIMIT:]
                        user_idx = truncated.find("User:")
                        history = truncated[user_idx:] if user_idx != -1 else truncated

            except Exception as e:
                end_time = time.perf_counter()
                duration = end_time - start_time
                print(f"  ❌ ERROR: {e} | Time: {duration:.2f}s")
                results.append((prompt, "ALLOWED", f"ERROR: {e}", False, duration))

    print("\\n" + "="*50)
    print(" TEST COMPLETE. GENERATING REPORT...")
    print("="*50)

    print_timed_table(results, title=f"Multi-Turn Stress Test ({len(STRESS_TEST_PROMPTS)} Turns)")

    # Format for standard log_utils (drop the duration for the markdown file since log_utils doesn't expect it)
    standard_rows = [(r[0], r[1], r[2], r[3]) for r in results]
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    save_markdown_report(standard_rows, title="Multi-Turn_Stress_Test_Timed", output_dir=reports_dir)

if __name__ == "__main__":
    asyncio.run(run_stress_test())
"""
tests/log_utils.py — Shared logging utilities for all test suites.
Provides table printing to stdout and Markdown report generation.
Import in any test file:
    from tests.log_utils import print_table, save_markdown_report
"""

import os
from datetime import datetime
from typing import List, Tuple

# Each row: (prompt, expected_outcome, actual_code, passed: bool)
Row = Tuple[str, str, str, bool]


def print_table(rows: List[Row], title: str = "Test Results") -> None:
    """Print a formatted ASCII table to stdout."""
    col_widths = [
        max(len("Prompt"), max(len(r[0][:60]) for r in rows)),
        max(len("Expected"), max(len(r[1]) for r in rows)),
        max(len("Actual (truncated)"), max(len(r[2][:50]) for r in rows)),
        max(len("Pass"), 4),
    ]

    def row_line(cols):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, col_widths)) + " |"

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"

    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    print(sep)
    print(row_line(["Prompt", "Expected", "Actual (truncated)", "Pass"]))
    print(sep)
    for prompt, expected, actual, passed in rows:
        p = "✅ PASS" if passed else "❌ FAIL"
        print(row_line([prompt[:60], expected, actual[:50], p]))
    print(sep)

    passed_count = sum(1 for r in rows if r[3])
    print(f"\n  Result: {passed_count}/{len(rows)} passed")
    print(f"{'=' * 70}\n")


def save_markdown_report(rows: List[Row], title: str, output_dir: str = "tests/reports") -> str:
    """Write a Markdown test report file and return the file path."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize title for filename
    safe_title = title.lower().replace(" ", "_").replace("/", "_")
    filepath = os.path.join(output_dir, f"{safe_title}_{timestamp}.md")

    passed_count = sum(1 for r in rows if r[3])
    total = len(rows)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Result:** {passed_count}/{total} passed\n\n")
        f.write("| # | Prompt | Expected | Actual (truncated) | Pass |\n")
        f.write("|---|--------|----------|--------------------|------|\n")
        for i, (prompt, expected, actual, passed) in enumerate(rows, 1):
            icon = "✅" if passed else "❌"
            actual_short = actual[:80].replace("\n", " ") if actual else ""
            f.write(f"| {i} | `{prompt[:70]}` | {expected} | `{actual_short}` | {icon} |\n")

        if passed_count < total:
            f.write("\n## ❌ Failed Cases\n\n")
            for prompt, expected, actual, passed in rows:
                if not passed:
                    f.write(f"### Prompt: `{prompt[:70]}`\n")
                    f.write(f"- **Expected:** {expected}\n")
                    f.write(f"- **Actual:**\n```lua\n{actual}\n```\n\n")

    print(f"  [log_utils] Report saved → {filepath}")
    return filepath

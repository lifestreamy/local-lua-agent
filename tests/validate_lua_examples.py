import argparse
import re
import subprocess
import sys
from pathlib import Path


def parse_examples(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"ЗАПРОС:\s*(.*?)\nКОД:\n(.*?)(?=\nЗАПРОС:|\Z)",
        re.DOTALL,
    )
    result: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        request = match.group(1).strip()
        code = match.group(2).strip()
        if code:
            result.append((request, code))
    return result


def validate_with_luac(code: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["luac", "-p", "-"],
            input=code.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
    except FileNotFoundError:
        return False, "luac not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "luac timed out"

    if proc.returncode == 0:
        return True, ""

    err = proc.stderr.decode("utf-8", errors="replace").strip()
    return False, err or "unknown luac error"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Lua examples from a text file via luac."
    )
    parser.add_argument(
        "--file",
        default="tests/test_base_cases_1.txt",
        help="Path to file with blocks: ЗАПРОС / КОД",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    examples = parse_examples(text)
    if not examples:
        print("[ERROR] No examples found. Expected blocks with 'ЗАПРОС:' and 'КОД:'.")
        return 1

    print(f"Found examples: {len(examples)}")
    print("-" * 60)

    passed = 0
    failed = 0

    for idx, (request, code) in enumerate(examples, start=1):
        ok, err = validate_with_luac(code)
        if ok:
            passed += 1
            print(f"[OK]   #{idx}: {request}")
        else:
            failed += 1
            print(f"[FAIL] #{idx}: {request}")
            print(f"       {err}")

    print("-" * 60)
    print(f"Total: {len(examples)} | Passed: {passed} | Failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

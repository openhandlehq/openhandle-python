#!/usr/bin/env python3
"""Score agent-authored SDK eval answers on type-checking and semantic markers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    answer_directory = Path(sys.argv[1] if len(sys.argv) > 1 else "evals/reference").resolve()
    tasks = json.loads((PACKAGE_ROOT / "evals" / "tasks.json").read_text())
    failing_files = type_check_failures(answer_directory)

    compile_score = 0
    semantic_score = 0
    for task in tasks:
        answer = answer_directory / f"{task['id']}.py"
        if not answer.exists():
            print(f"{task['id']}: compile=fail semantic=fail (missing file)")
            continue
        source = answer.read_text()
        compiles = answer not in failing_files
        required = all(marker in source for marker in task["required"])
        forbidden = all(marker not in source for marker in task.get("forbidden", []))
        uses_public_package = "from openhandle" in source and "openhandle._" not in source
        semantic = required and forbidden and uses_public_package
        if compiles:
            compile_score += 1
        if semantic:
            semantic_score += 1
        print(f"{task['id']}: compile={'pass' if compiles else 'fail'} semantic={'pass' if semantic else 'fail'}")

    print(f"Agent SDK eval: compile {compile_score}/{len(tasks)}, semantic {semantic_score}/{len(tasks)}")
    return 0 if compile_score == len(tasks) and semantic_score == len(tasks) else 1


def type_check_failures(answer_directory: Path) -> set[Path]:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-error-summary", str(answer_directory)],
        capture_output=True,
        cwd=PACKAGE_ROOT,
        text=True,
    )
    failures: set[Path] = set()
    for line in result.stdout.splitlines():
        location = line.split(":", 1)[0]
        if location.endswith(".py"):
            failures.add((PACKAGE_ROOT / location).resolve())
    if result.returncode != 0:
        print(result.stdout, end="")
    return failures


if __name__ == "__main__":
    sys.exit(main())

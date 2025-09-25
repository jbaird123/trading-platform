#!/usr/bin/env python3
"""Run pytest coverage only for staged source files.

This pre-commit helper enforces 100% coverage on the Python files staged for
commit under ``src/trading_platform``. It queries the staged file list,
filters down to relevant modules, and runs pytest with ``--cov`` limited to
those paths. If no source files are staged, the check is skipped.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "trading_platform"


def _staged_source_files() -> list[Path]:
    """Return staged Python files under ``src/trading_platform``."""

    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMR",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive guard
        print("Failed to determine staged files:", exc, file=sys.stderr)
        return []

    staged_paths: list[Path] = []
    for rel_path in result.stdout.splitlines():
        path = (REPO_ROOT / rel_path).resolve()
        if path.suffix != ".py":
            continue
        if not path.exists():
            continue
        if SRC_ROOT in path.parents or path == SRC_ROOT:
            staged_paths.append(path)
    return staged_paths


def main() -> int:
    os.chdir(REPO_ROOT)

    src_files = sorted({path for path in _staged_source_files()})
    if not src_files:
        print(
            "No staged source files under src/trading_platform; "
            "skipping coverage check."
        )
        return 0

    coverage_targets = [str(path.relative_to(REPO_ROOT)) for path in src_files]
    pytest_cmd = [
        "poetry",
        "run",
        "pytest",
        "--cov-config=.coveragerc",
        "--cov-report=term",
        "--cov-fail-under=100",
    ] + [f"--cov={target}" for target in coverage_targets]

    pretty_cmd = " ".join(shlex.quote(part) for part in pytest_cmd)
    print(f"Running targeted coverage: {pretty_cmd}")

    completed = subprocess.run(pytest_cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

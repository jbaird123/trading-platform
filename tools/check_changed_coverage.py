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
TESTS_ROOT = REPO_ROOT / "tests"


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


def _to_module_name(path: Path) -> str:
    """Translate a source path into an importable module name."""

    relative_path = path.relative_to(SRC_ROOT)
    parts = list(relative_path.parts)
    if not parts:
        return "trading_platform"

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")

    module_parts = ["trading_platform"] + [part for part in parts if part]
    return ".".join(module_parts)


def _contains_module_reference(
    test_file: Path,
    *,
    module_name: str,
    cache: dict[Path, str],
) -> bool:
    """Return True if the test file references the target module."""

    if test_file in cache:
        content = cache[test_file]
    else:
        try:
            content = test_file.read_text()
        except OSError:
            cache[test_file] = ""
            return False
        cache[test_file] = content

    if module_name in content:
        return True

    if "." in module_name:
        parent, child = module_name.rsplit(".", 1)
        direct_import = f"from {parent} import {child}"
        if direct_import in content:
            return True

    return False


def _candidate_tests_for(
    path: Path,
    test_files: list[Path],
    *,
    module_name: str,
    cache: dict[Path, str],
) -> list[Path]:
    """Return test files that likely exercise ``path``."""

    base_name = path.stem
    if base_name == "__init__":
        base_name = path.parent.name

    base_name_lower = base_name.lower()
    relative_parent = path.relative_to(SRC_ROOT).parent
    parent_parts = list(relative_parent.parts)
    top_level = parent_parts[0].lower() if parent_parts else None

    matches: list[Path] = []
    for test_file in test_files:
        test_rel_parts = [
            part.lower() for part in test_file.relative_to(TESTS_ROOT).parts
        ]
        if top_level and top_level in test_rel_parts:
            matches.append(test_file)
            continue
        if base_name_lower in test_file.stem.lower():
            matches.append(test_file)
            continue
        if _contains_module_reference(test_file, module_name=module_name, cache=cache):
            matches.append(test_file)

    return matches


def main() -> int:
    os.chdir(REPO_ROOT)

    src_files = sorted({path for path in _staged_source_files()})
    if not src_files:
        print(
            "No staged source files under src/trading_platform; "
            "skipping coverage check."
        )
        return 0

    module_names = {path: _to_module_name(path) for path in src_files}
    coverage_targets = list(module_names.values())

    # Precompute available test files under tests/
    if TESTS_ROOT.exists():
        all_test_files = sorted(TESTS_ROOT.rglob("test_*.py"))
    else:
        all_test_files = []

    test_targets: set[Path] = set()
    content_cache: dict[Path, str] = {}
    for path in src_files:
        module_name = module_names[path]
        for test_file in _candidate_tests_for(
            path,
            all_test_files,
            module_name=module_name,
            cache=content_cache,
        ):
            test_targets.add(test_file)

    pytest_cmd = [
        "poetry",
        "run",
        "pytest",
        "--cov-config=.coveragerc",
        "--cov-report=term",
        "--cov-fail-under=100",
    ] + [f"--cov={target}" for target in coverage_targets]

    if test_targets:
        pytest_cmd.extend(
            str(path.relative_to(REPO_ROOT)) for path in sorted(test_targets)
        )
    else:
        pytest_cmd.append("tests")

    pretty_cmd = " ".join(shlex.quote(part) for part in pytest_cmd)
    print(f"Running targeted coverage: {pretty_cmd}")

    completed = subprocess.run(pytest_cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

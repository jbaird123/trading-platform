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


def _staged_files() -> tuple[list[Path], list[Path]]:
    """Return staged Python files under ``src/trading_platform`` and ``tests``."""

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
        return [], []

    staged_src_paths: list[Path] = []
    staged_test_paths: list[Path] = []
    for rel_path in result.stdout.splitlines():
        path = (REPO_ROOT / rel_path).resolve()
        if path.suffix != ".py":
            continue
        if not path.exists():
            continue
        if SRC_ROOT in path.parents or path == SRC_ROOT:
            staged_src_paths.append(path)
        elif TESTS_ROOT in path.parents or path == TESTS_ROOT:
            staged_test_paths.append(path)
    return staged_src_paths, staged_test_paths


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


def _test_file_to_module_dir(test_path: Path) -> str | None:
    """Map a test file to its corresponding module directory for coverage.

    For example:
    - tests/ai/llm_analysis/test_client.py -> trading_platform.ai.llm_analysis
    - tests/core/test_rem.py -> trading_platform.core
    """
    try:
        relative_path = test_path.relative_to(TESTS_ROOT)
    except ValueError:
        return None

    parts = list(relative_path.parts)
    if not parts:
        return None

    # Remove the test filename and build module path
    dir_parts = parts[:-1]  # Remove test_*.py filename

    if not dir_parts:
        return None

    module_parts = ["trading_platform"] + dir_parts
    return ".".join(module_parts)


def _get_test_directory(test_path: Path) -> Path | None:
    """Get the test directory that should be run for complete coverage.

    For example:
    - tests/ai/llm_analysis/test_client.py -> tests/ai/llm_analysis
    - tests/core/test_rem.py -> tests/core
    """
    try:
        relative_path = test_path.relative_to(TESTS_ROOT)
    except ValueError:
        return None

    parts = list(relative_path.parts)
    if not parts:
        return None

    # Return the directory containing the test file
    dir_parts = parts[:-1]  # Remove test_*.py filename

    if not dir_parts:
        return TESTS_ROOT

    return TESTS_ROOT / Path(*dir_parts)


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

    src_files, test_files = _staged_files()

    if not src_files and not test_files:
        print(
            "No staged Python files under src/trading_platform or tests; "
            "skipping coverage check."
        )
        return 0

    coverage_targets: set[str] = set()
    test_directories: set[Path] = set()

    # Handle staged source files
    if src_files:
        for src_file in src_files:
            module_name = _to_module_name(src_file)
            coverage_targets.add(module_name)

        # Only find test files for source files if no test files are staged
        if not test_files:
            if TESTS_ROOT.exists():
                all_test_files = sorted(TESTS_ROOT.rglob("test_*.py"))
            else:
                all_test_files = []

            content_cache: dict[Path, str] = {}
            for src_file in src_files:
                module_name = _to_module_name(src_file)
                for test_file in _candidate_tests_for(
                    src_file,
                    all_test_files,
                    module_name=module_name,
                    cache=content_cache,
                ):
                    test_dir = _get_test_directory(test_file)
                    if test_dir:
                        test_directories.add(test_dir)

    # Handle staged test files - map them to their module directories
    if test_files:
        for test_file in test_files:
            # Add the module this test covers to coverage targets
            test_module_name: str | None = _test_file_to_module_dir(test_file)
            if test_module_name:
                coverage_targets.add(test_module_name)

            # Add the test directory to run all tests for complete coverage
            test_dir = _get_test_directory(test_file)
            if test_dir and test_dir.exists():
                test_directories.add(test_dir)

    if not coverage_targets:
        print("No coverage targets identified; skipping coverage check.")
        return 0

    pytest_cmd = [
        "poetry",
        "run",
        "pytest",
        "--cov-config=.coveragerc",
        "--cov-report=term",
        "--cov-fail-under=100",
    ] + [f"--cov={target}" for target in sorted(coverage_targets)]

    if test_directories:
        pytest_cmd.extend(
            str(path.relative_to(REPO_ROOT)) for path in sorted(test_directories)
        )
    else:
        pytest_cmd.append("tests")

    pretty_cmd = " ".join(shlex.quote(part) for part in pytest_cmd)
    print(f"Running targeted coverage: {pretty_cmd}")

    completed = subprocess.run(pytest_cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

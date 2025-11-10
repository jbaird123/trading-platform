#!/usr/bin/env python3
"""Run all hash-based golden tests and auto-diff any failures.

This script is meant to be the one-stop "something failed, show me why"
entry point for the EMA crossover golden validations. It performs the
following steps:

1. Runs the three pytest modules that enforce SHA256 hashes:
     • Platform trade snapshots
     • Exit price comparison CSVs
     • Exit time comparison CSVs
2. Captures any failure message that mentions a hash mismatch.
3. For each failing strategy, automatically invokes `scripts/golden_compare.py`
   so you get a row/column level diff without re-entering paths.

Example:
    poetry run python scripts/run_golden_hash_checks.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Pattern

from trading_platform.data.handler import DataHandler

from scripts.check_golden_trades import (
    DEFAULT_DATA_ROOT as DEFAULT_TV_DATA_ROOT,
)
from scripts.check_golden_trades import (
    DEFAULT_INDEX,
    ensure_output_dir,
    export_trades,
)
from scripts.check_golden_trades import (
    DEFAULT_OUTPUT_DIR as DEFAULT_TRADE_OUTPUT_DIR,
)
from scripts.check_golden_trades import (
    STRATEGIES as TRADE_OUTPUT_NAMES,
)
from scripts.golden_compare import compare_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STRATEGY_ROOT = PROJECT_ROOT / "data/dvc/golden/strategies"
EXPORT_WORKSPACE = PROJECT_ROOT / "workspace/comparison_exports"

PRICE_REGEX = re.compile(r"Comparison file hash mismatch for ([^!]+)!")
TRADE_REGEX = re.compile(r"Platform trades hash mismatch for ([^!]+)!")


@dataclass
class GoldenSpec:
    """Represents one pytest command we need to run and monitor."""

    name: str
    pytest_targets: list[str]
    failure_regex: Pattern[str]
    on_failure: Callable[[str], None]


def run_pytest(
    args: Iterable[str],
    *,
    show_output: bool = False,
) -> tuple[int, str]:
    """Run pytest with the given arguments and return (exit_code, combined_output)."""

    cmd = [sys.executable, "-m", "pytest", "--maxfail=0", *args]
    printable = " ".join(cmd)
    if show_output:
        print(f"\n$ {printable}\n", flush=True)

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if show_output:
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)

    combined = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, combined


def build_exit_diff_fn(
    comparison_type: str,
    golden_filename: str,
) -> Callable[[str], None]:
    """Return a function that diffs the requested exit comparison CSV."""

    def _run(strategy_name: str) -> None:
        strategy_name = _normalize_strategy_name(strategy_name)
        slug = strategy_name.replace("/", "_")
        workspace_path = EXPORT_WORKSPACE / f"{slug}_{comparison_type}.csv"
        golden_path = STRATEGY_ROOT / strategy_name / golden_filename

        header = (
            f"\n{'=' * 80}\n"
            f"{comparison_type.upper()} diff for {strategy_name}\n"
            f"{'=' * 80}"
        )
        print(header)
        if not workspace_path.exists():
            print(f"⚠️  Workspace file missing: {workspace_path}")
            print(
                "    Ensure the exit comparison test writes the CSV "
                "(re-run with --show-pytest-output for details)."
            )
            return
        if not golden_path.exists():
            print(f"⚠️  Golden file missing: {golden_path}")
            return
        compare_paths(workspace_path, golden_path, index_cols=None)

    return _run


def build_trade_diff_fn(
    data_handler: DataHandler,
    output_dir: Path,
) -> Callable[[str], None]:
    """Return a function that rebuilds platform trades and diffs them."""

    ensure_output_dir(output_dir)

    def _run(strategy_name: str) -> None:
        strategy_name = _normalize_strategy_name(strategy_name)
        filename = TRADE_OUTPUT_NAMES.get(
            strategy_name,
            f"{strategy_name.replace('/', '_')}_platform_trades.csv",
        )
        output_path = output_dir / filename
        golden_path = STRATEGY_ROOT / strategy_name / "platform_trades_golden.csv"

        header = (
            f"\n{'=' * 80}\n"
            f"Platform trades diff for {strategy_name}\n"
            f"{'=' * 80}"
        )
        print(header)
        try:
            export_trades(strategy_name, output_path, data_handler)
        except FileNotFoundError as exc:
            print(f"⚠️  {exc}")
            return

        if not golden_path.exists():
            print(f"⚠️  Golden file missing: {golden_path}")
            return

        compare_paths(output_path, golden_path, index_cols=DEFAULT_INDEX)

    return _run


def _normalize_strategy_name(name: str) -> str:
    stripped = name.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        stripped = stripped[1:-1]
    return stripped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trade-output-dir",
        type=Path,
        default=DEFAULT_TRADE_OUTPUT_DIR,
        help="Directory for regenerated platform trade CSVs "
        "(default: workspace/golden_comparison)",
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        help="Optional whitelist of strategy names. When provided, diffs are only "
        "generated for the listed strategies even if multiple tests failed.",
    )
    parser.add_argument(
        "--show-pytest-output",
        action="store_true",
        help="Print the full pytest stdout/stderr for each suite (default: only show a "
        "pass/fail summary).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    whitelist = (
        {_normalize_strategy_name(name) for name in args.strategies}
        if args.strategies
        else None
    )

    data_handler = DataHandler(symbol="EUR_USD", data_root=DEFAULT_TV_DATA_ROOT)
    specs = [
        GoldenSpec(
            name="Platform trade hashes",
            pytest_targets=[
                "tests/validation/test_strategy_validation.py::"
                "test_ema_crossover_platform_trades_match_golden"
            ],
            failure_regex=TRADE_REGEX,
            on_failure=build_trade_diff_fn(data_handler, args.trade_output_dir),
        ),
        GoldenSpec(
            name="Exit price comparisons",
            pytest_targets=[
                "tests/validation/test_export_exit_price_comparison.py::"
                "test_exit_price_comparison_matches_golden"
            ],
            failure_regex=PRICE_REGEX,
            on_failure=build_exit_diff_fn(
                comparison_type="exit_price",
                golden_filename="exit_price_comparison_golden.csv",
            ),
        ),
        GoldenSpec(
            name="Exit time comparisons",
            pytest_targets=[
                "tests/validation/test_export_exit_time_comparison.py::"
                "test_exit_time_comparison_matches_golden"
            ],
            failure_regex=PRICE_REGEX,
            on_failure=build_exit_diff_fn(
                comparison_type="exit_time",
                golden_filename="exit_time_comparison_golden.csv",
            ),
        ),
    ]

    overall_success = True

    for spec in specs:
        print(f"\n=== Running {spec.name} ===")
        exit_code, output = run_pytest(
            spec.pytest_targets, show_output=args.show_pytest_output
        )
        result_label = "PASS" if exit_code == 0 else f"FAIL (code {exit_code})"
        if not args.show_pytest_output:
            print(f"Pytest result: {result_label}")
            if exit_code != 0:
                print("  (re-run with --show-pytest-output to see full logs)")
        if exit_code != 0:
            overall_success = False

        raw_matches = {match.strip() for match in spec.failure_regex.findall(output)}
        matches = {_normalize_strategy_name(match) for match in raw_matches}
        if not matches:
            if exit_code != 0:
                print(
                    "⚠️  Pytest failed but no hash mismatch lines were detected. "
                    "See output above for details."
                )
            continue

        for strategy in sorted(matches):
            if whitelist and strategy not in whitelist:
                print(f"Skipping diff for {strategy} (not in --strategies)")
                continue
            spec.on_failure(strategy)

    if overall_success:
        print("\n✅  All golden hash tests passed.")
        sys.exit(0)

    print("\n⚠️  Golden hash tests failed. Review the diffs above.")
    sys.exit(1)


if __name__ == "__main__":
    main()

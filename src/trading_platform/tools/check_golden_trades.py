#!/usr/bin/env python3
"""Rebuild EMA crossover trade exports and diff them against golden files.

This script automates the manual workflow under `workspace/golden_comparison/`:
  1. Executes the golden strategy backtests to export fresh trade CSVs.
  2. Runs the reusable golden comparator for each strategy, producing row/column
     mismatch summaries.

Example:
    poetry run python scripts/check_golden_trades.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from trading_platform.data.handler import DataHandler
from trading_platform.tools.golden_compare import compare_paths

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from tests.validation.test_strategy_validation import load_platform_trades  # noqa: E402

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "workspace/golden_comparison"
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data/dvc/golden/ohlcv/tradingview"
STRATEGY_ROOT = PROJECT_ROOT / "data/dvc/golden/strategies"
CONFIG_ROOT = PROJECT_ROOT / "configs/golden_strategies"
DEFAULT_INDEX = ["entry_time", "exit_time", "side", "entry_price", "exit_price"]

STRATEGIES = {
    "ema_crossover/baseline": "ema_crossover_baseline_new_platform_trades.csv",
    "ema_crossover/20pip_stop": "ema_crossover_20pip_stop_new_platform_trades.csv",
    "ema_crossover/20pip_stop_40pip_tp": (
        "ema_crossover_20pip_stop_40pip_tp_new_platform_trades.csv"
    ),
    "ema_crossover/20pip_trailing_stop": (
        "ema_crossover_20pip_trailing_stop_new_platform_trades.csv"
    ),
    "ema_crossover/20pip_trailing_stop_15pip_tp": (
        "ema_crossover_20pip_trailing_stop_15pip_tp_new_platform_trades.csv"
    ),
    "ema_crossover/2atr_stop": "ema_crossover_2atr_stop_new_platform_trades.csv",
    "ema_crossover/bb_stop": "ema_crossover_bb_stop_new_platform_trades.csv",
}


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_strategy_artifacts(strategy: str) -> tuple[dict, dict, pd.DataFrame]:
    data_dir = STRATEGY_ROOT / strategy
    config_dir = CONFIG_ROOT / strategy
    metadata_path = data_dir / "metadata.json"
    run_config_path = config_dir / "run_config.yaml"
    ohlcv_path = data_dir / "ohlcv.csv"

    if (
        not metadata_path.exists()
        or not run_config_path.exists()
        or not ohlcv_path.exists()
    ):
        raise FileNotFoundError(f"Missing artifacts for {strategy}")

    with metadata_path.open() as fh:
        metadata = json.load(fh)
    with run_config_path.open() as fh:
        run_config = yaml.safe_load(fh)

    ohlcv = pd.read_csv(ohlcv_path, index_col=0, parse_dates=True)
    return metadata, run_config, ohlcv


def export_trades(
    strategy: str,
    output_path: Path,
    handler: DataHandler,
) -> None:
    metadata, run_config, ohlcv = load_strategy_artifacts(strategy)
    date_range = metadata.get("date_range")

    trades = load_platform_trades(
        strategy_name=strategy,
        run_config=run_config,
        ohlcv_data=ohlcv,
        data_handler=handler,
        date_range=date_range,
    )

    df = pd.DataFrame(trades)
    if df.empty:
        print(f"⚠️  No trades produced for {strategy}; writing empty file.")
    else:
        sort_keys = [col for col in DEFAULT_INDEX if col in df.columns]
        if sort_keys:
            df = df.sort_values(sort_keys).reset_index(drop=True)

    df.to_csv(output_path, index=False)
    try:
        display_path = output_path.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = output_path
    print(f"Saved {len(df)} trades -> {display_path}")


def compare_strategy(strategy: str, new_file: Path) -> None:
    golden_file = STRATEGY_ROOT / strategy / "platform_trades_golden.csv"
    if not golden_file.exists():
        print(f"⚠️  Golden file missing: {golden_file}")
        return
    print("\n" + "=" * 80)
    print(f"Strategy: {strategy}")
    print("=" * 80)
    compare_paths(new_file, golden_file, index_cols=DEFAULT_INDEX)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory to write regenerated CSVs "
            "(default: workspace/golden_comparison)"
        ),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help=(
            "OHLC root for running the backtests " "(default: TradingView golden data)"
        ),
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        help=(
            "Optional subset of strategies to check "
            "(defaults to all EMA crossover variants)"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = ensure_output_dir(args.output_dir)

    if not args.data_root.exists():
        raise FileNotFoundError(
            "Data root "
            f"{args.data_root} does not exist; run `dvc pull {args.data_root}` "
            "first."
        )

    handler = DataHandler(symbol="EUR_USD", data_root=args.data_root)
    selected = args.strategies or list(STRATEGIES.keys())

    for strategy in selected:
        if strategy not in STRATEGIES:
            print(f"⚠️  Unknown strategy '{strategy}', skipping.")
            continue
        output_path = output_dir / STRATEGIES[strategy]
        ensure_output_dir(output_path.parent)
        export_trades(strategy, output_path, handler)
        compare_strategy(strategy, output_path)


if __name__ == "__main__":
    main()

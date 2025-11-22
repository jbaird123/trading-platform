#!/usr/bin/env python3
"""
Generate golden platform trades files for all strategies.

This script runs backtests for each golden strategy and saves the platform
trades output as golden reference files for hash-based verification.

USAGE:
    poetry run python tests/validation/generate_golden_trades.py

WHEN TO RUN:
    - After adding a new golden strategy
    - After intentionally changing platform behavior (and wanting to update
      golden files)
    - After modifying trade output fields

OUTPUT:
    Creates platform_trades_golden.csv for each strategy in:
    data/dvc/golden/strategies/<strategy_name>/

FIELDS INCLUDED:
    - All base trade fields: symbol, side, size, timestamps, prices, pnl, etc.
    - Metrics: mfe_currency, mae_currency, bars_held
    - Costs: cost_currency, spread, commission, slippage
    - Context: All flattened context_at_entry fields
    - EXCLUDES: r_multiple (only relevant when stop-loss exists at entry)

IMPORTANT:
    After regenerating golden files, you must:
    1. Add to DVC: poetry run dvc add data/dvc/golden/strategies/ema_crossover
    2. Commit: git add data/dvc/golden/strategies/ema_crossover.dvc
    3. Push DVC: poetry run dvc push
    4. Push Git: git push
"""

import csv
import sys
from pathlib import Path

# Ensure project root on sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from trading_platform.data.handler import DataHandler  # noqa: E402

from tests.validation.test_strategy_validation import load_platform_trades  # noqa: E402


def generate_golden_trades_for_strategy(
    strategy_name: str,
    output_path: Path,
    exclude_fields: list[str] | None = None,
) -> None:
    """Generate golden trades file for a strategy.

    Args:
        strategy_name: Name like "ema_crossover/baseline"
        output_path: Where to save platform_trades_golden.csv
        exclude_fields: Fields to exclude (e.g., ["r_multiple"])
    """
    if exclude_fields is None:
        exclude_fields = ["r_multiple"]

    print(f"\n{'='*80}")
    print(f"Generating golden trades for: {strategy_name}")
    print(f"{'='*80}")

    # SAFETY CHECK: Never overwrite existing golden files!
    if output_path.exists():
        raise FileExistsError(
            f"Golden file already exists: {output_path}\n"
            f"Golden files are immutable and should NEVER be regenerated.\n"
            f"If you need to update this file, you must:\n"
            f"  1. Manually delete the existing file\n"
            f"  2. Remove it from DVC tracking\n"
            f"  3. Re-run this script\n"
            f"  4. Verify all tests still pass\n"
            f"This is intentionally difficult to prevent accidental changes to "
            f"golden data."
        )

    # Load golden data
    # Navigate to project root: tests/validation -> tests -> project_root
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data/dvc/golden/strategies" / strategy_name

    # Load TradingView OHLCV
    ohlcv_path = data_dir / "ohlcv.csv"
    if not ohlcv_path.exists():
        raise FileNotFoundError(f"OHLCV not found: {ohlcv_path}")

    ohlcv = pd.read_csv(ohlcv_path, index_col=0, parse_dates=True)
    ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)

    # Load metadata for date range
    metadata_path = data_dir / "metadata.json"
    with open(metadata_path) as f:
        import json

        metadata = json.load(f)

    date_range = metadata.get("date_range")

    strategy_dir = project_root / f"configs/golden_strategies/{strategy_name}"

    # Load REM config if exists
    rem_path = strategy_dir / "rem.yaml"
    rem_config = None
    if rem_path.exists():
        with open(rem_path) as f:
            rem_config = yaml.safe_load(f)

    # Load run config
    run_config_path = strategy_dir / "run_config.yaml"
    with open(run_config_path) as f:
        run_config_dict = yaml.safe_load(f)

    # Add REM config if available
    if rem_config:
        run_config_dict["rem_config"] = rem_config

    # ALL strategies now use 1-minute data resampled to 1H for consistency
    # This ensures all tests use the same data processing pipeline as production
    print("Loading 1-minute data for strategy...")
    data_root = project_root / "data/dvc/golden/ohlcv/tradingview"

    if not data_root.exists():
        raise FileNotFoundError(f"Data root not found: {data_root}")

    data_handler = DataHandler(
        symbol="EUR_USD",
        data_root=data_root,
    )

    # Use resampled 1H data from DataHandler (includes actual volume)
    ohlcv_1h = data_handler.get_data(timeframe="1H")

    # Run through the same backtester pipeline the tests use
    print(f"Running backtest with {len(ohlcv_1h)} bars via load_platform_trades...")
    trades = load_platform_trades(
        strategy_name=strategy_name,
        run_config=run_config_dict,
        ohlcv_data=ohlcv,
        data_handler=data_handler,
        date_range=date_range,
    )

    print(f"Total trades after filtering: {len(trades)}")

    # Convert to dictionaries with all fields except excluded ones
    rows = []
    for trade in trades:
        row = {
            "symbol": trade["symbol"],
            "side": trade["side"],
            "size": trade["size"],
            "entry_time": trade["entry_time"],
            "exit_time": trade["exit_time"],
            "entry_price": trade["entry_price"],
            "exit_price": trade["exit_price"],
            "exit_reason": trade["exit_reason"],
            "pnl": trade["pnl"],
            "mfe_currency": trade["mfe_currency"],
            "mae_currency": trade["mae_currency"],
            "bars_held": trade["bars_held"],
            "cost_currency": trade["cost_currency"],
            "spread": trade.get("spread", 0.0),
            "commission": trade.get("commission", 0.0),
            "slippage": trade.get("slippage", 0.0),
        }

        # Add context fields (already flattened by load_platform_trades)
        for key, value in trade.items():
            if key.startswith("ctx_"):
                row[key] = value

        rows.append(row)

    # Save to CSV
    if rows:
        # Get all field names (base + context fields)
        all_fields: set[str] = set()
        for row in rows:
            all_fields.update(row.keys())

        # Order fields: base fields first, then context fields sorted
        base_fields = [
            "symbol",
            "side",
            "size",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "exit_reason",
            "pnl",
            "mfe_currency",
            "mae_currency",
            "bars_held",
            "cost_currency",
            "spread",
            "commission",
            "slippage",
        ]
        context_fields = sorted([f for f in all_fields if f.startswith("ctx_")])
        ordered_fields = base_fields + context_fields

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ordered_fields)
            writer.writeheader()
            writer.writerows(rows)

        print(f"✓ Saved {len(rows)} trades to: {output_path}")
    else:
        print("⚠ No trades to save!")


def _flatten_context(ctx: dict, prefix: str = "") -> dict:
    """Flatten nested context dict into dot-notation keys."""
    result = {}
    for key, value in ctx.items():
        new_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            # Recursively flatten nested dicts
            result.update(_flatten_context(value, f"{new_key}_"))
        else:
            result[new_key] = value
    return result


def main():
    """Generate golden trades for all strategies."""
    # Navigate to project root
    project_root = Path(__file__).parent.parent.parent

    strategies = [
        "ema_crossover/baseline",
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "ema_crossover/2atr_stop",
        "ema_crossover/bb_stop",
    ]

    for strategy_name in strategies:
        output_path = (
            project_root
            / "data/dvc/golden/strategies"
            / strategy_name
            / "platform_trades_golden.csv"
        )

        try:
            generate_golden_trades_for_strategy(strategy_name, output_path)
        except Exception as e:
            print(f"✗ Failed to generate golden trades for {strategy_name}: {e}")
            import traceback

            traceback.print_exc()
            continue

    print(f"\n{'='*80}")
    print("Golden trades generation complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

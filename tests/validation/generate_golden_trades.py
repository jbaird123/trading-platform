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
from pathlib import Path

import pandas as pd
import yaml
from trading_platform.backtester.orchestrator import run_backtest_from_config
from trading_platform.core.config import RunConfig
from trading_platform.data.handler import DataHandler


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

    # Add volume column if missing (not needed for strategies but required
    # by backtester). Use 1.0 to match conftest.py fixture behavior
    if "volume" not in ohlcv.columns:
        ohlcv["volume"] = 1.0

    # Load metadata for date range
    metadata_path = data_dir / "metadata.json"
    with open(metadata_path) as f:
        import json

        metadata = json.load(f)

    date_range = metadata.get("date_range")

    # Filter OHLCV to extended range [warmup_start, validation_end]
    if date_range:
        from datetime import timedelta

        end_date = pd.to_datetime(date_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )
        warmup_start = pd.Timestamp("2022-12-01", tz="UTC")
        ohlcv_filtered = ohlcv[
            (ohlcv.index >= warmup_start) & (ohlcv.index <= end_date)
        ].copy()
    else:
        ohlcv_filtered = ohlcv

    # Load strategy config
    strategy_dir = project_root / f"configs/golden_strategies/{strategy_name}"
    strategy_path = strategy_dir / "strategy.yaml"

    with open(strategy_path) as f:
        strategy_config = yaml.safe_load(f)

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

    # Override warmup_bars to 0 when using extended data
    if date_range:
        run_config_dict["warmup_bars"] = 0

    # Create RunConfig
    config = RunConfig.model_validate(run_config_dict)

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

    # Apply same date filtering
    if date_range:
        ohlcv_filtered = ohlcv_1h[
            (ohlcv_1h.index >= warmup_start) & (ohlcv_1h.index <= end_date)
        ].copy()
    else:
        ohlcv_filtered = ohlcv_1h

    # Run backtest
    print(f"Running backtest with {len(ohlcv_filtered)} bars...")
    results = run_backtest_from_config(
        config=config,
        market_data=ohlcv_filtered,
        strategy_config=strategy_config,
        data_handler=data_handler,
    )

    # Filter trades to validation range
    trades_list = []
    if date_range:
        val_start = pd.to_datetime(date_range["start"], utc=True)
        val_end = pd.to_datetime(date_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )

        for trade in results["trades"]:
            if trade.exit_reason == "end_of_data":
                continue
            if val_start <= trade.entry_time <= val_end:
                trades_list.append(trade)
    else:
        trades_list = [t for t in results["trades"] if t.exit_reason != "end_of_data"]

    print(f"Total trades after filtering: {len(trades_list)}")

    # Convert to dictionaries with all fields except excluded ones
    rows = []
    for trade in trades_list:
        row = {
            "symbol": trade.symbol,
            "side": trade.side,
            "size": trade.size,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "exit_reason": trade.exit_reason,
            "pnl": trade.pnl,
            "mfe_currency": trade.mfe_currency,
            "mae_currency": trade.mae_currency,
            "bars_held": trade.bars_held,
            "cost_currency": trade.cost_currency,
        }

        # Add cost breakdown fields
        if trade.cost_breakdown:
            row["spread"] = trade.cost_breakdown.get("spread", 0.0)
            row["commission"] = trade.cost_breakdown.get("commission", 0.0)
            row["slippage"] = trade.cost_breakdown.get("slippage", 0.0)
        else:
            row["spread"] = 0.0
            row["commission"] = 0.0
            row["slippage"] = 0.0

        # Add context fields (flattened)
        if trade.context_at_entry:
            for key, value in _flatten_context(trade.context_at_entry).items():
                row[f"ctx_{key}"] = value

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

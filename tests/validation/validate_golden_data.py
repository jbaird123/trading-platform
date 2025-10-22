#!/usr/bin/env python3
"""Validate TradingView golden data exports before running tests.

This script checks for common issues in TradingView exports that cause test failures:
- Missing volume column in OHLCV data
- Wrong timezone (should be "UTC (Reykjavik)" not "UTC (Azores)")
- Date range mismatches
- Missing required files
- Invalid metadata format

USAGE:
    poetry run python tests/validation/validate_golden_data.py \\
        --strategy ema_crossover/atr_stop
    poetry run python tests/validation/validate_golden_data.py --all

EXIT CODES:
    0: All validations passed
    1: Validation errors found
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


class ValidationError:
    """A validation error with category, message, and fix suggestion."""

    def __init__(self, category: str, message: str, fix: str):
        self.category = category
        self.message = message
        self.fix = fix

    def __str__(self) -> str:
        return f"❌ {self.category}: {self.message}\n   Fix: {self.fix}"


def validate_strategy(strategy_name: str, project_root: Path) -> List[ValidationError]:
    """Validate all golden data for a strategy.

    Args:
        strategy_name: Strategy name like "ema_crossover/atr_stop"
        project_root: Project root directory

    Returns:
        List of validation errors (empty if all checks pass)
    """
    errors: List[ValidationError] = []
    data_dir = project_root / "data/dvc/golden/strategies" / strategy_name

    print(f"\n{'='*80}")
    print(f"Validating: {strategy_name}")
    print(f"{'='*80}\n")

    # Check 1: Required files exist
    required_files = {
        "metadata.json": "Metadata configuration",
        "ohlcv.csv": "TradingView OHLCV export",
        "trades.csv": "TradingView trades export",
    }

    for filename, description in required_files.items():
        file_path = data_dir / filename
        if not file_path.exists():
            errors.append(
                ValidationError(
                    category="MISSING_FILE",
                    message=f"{description} not found: {file_path}",
                    fix=f"Export {description} from TradingView and save to {file_path}",  # noqa: E501
                )
            )

    # If metadata missing, can't proceed with other checks
    if not (data_dir / "metadata.json").exists():
        return errors

    # Load metadata
    with open(data_dir / "metadata.json") as f:
        metadata = json.load(f)

    # Check 2: Metadata has required fields
    required_metadata_fields = {
        "dataset_type": str,
        "strategy_name": str,
        "tradingview_version": str,
        "export_date": str,
        "date_range": dict,
        "instrument": str,
        "timeframe": str,
        "exit_mechanisms": list,
        "timezone": str,
    }

    for field, expected_type in required_metadata_fields.items():
        if field not in metadata:
            errors.append(
                ValidationError(
                    category="MISSING_METADATA",
                    message=f"metadata.json missing required field '{field}'",
                    fix=f"Add '{field}': <value> to metadata.json",
                )
            )
        elif not isinstance(metadata.get(field), expected_type):
            errors.append(
                ValidationError(
                    category="INVALID_METADATA",
                    message=(
                        f"metadata.json field '{field}' should be {expected_type.__name__}, "  # noqa: E501
                        f"got {type(metadata.get(field)).__name__}"
                    ),
                    fix=f"Change '{field}' to {expected_type.__name__} in metadata.json",  # noqa: E501
                )
            )

    # Check 3: Timezone is correct
    timezone = metadata.get("timezone", "")
    if timezone != "UTC (Reykjavik)":
        errors.append(
            ValidationError(
                category="WRONG_TIMEZONE",
                message=f"Timezone is '{timezone}' but should be 'UTC (Reykjavik)'",
                fix=(
                    "Change TradingView chart timezone to 'UTC (Reykjavik)' and re-export. "  # noqa: E501
                    "Click chart settings → Timezone → UTC (Reykjavik)"
                ),
            )
        )

    # Check 4: OHLCV has volume column
    ohlcv_path = data_dir / "ohlcv.csv"
    if ohlcv_path.exists():
        ohlcv = pd.read_csv(ohlcv_path, index_col=0, parse_dates=True)

        if "volume" not in ohlcv.columns:
            errors.append(
                ValidationError(
                    category="MISSING_VOLUME",
                    message="OHLCV data missing 'volume' column",
                    fix=(
                        "Add volume column to ohlcv.csv with value 1.0 for all rows, "
                        "or re-export from TradingView with volume enabled"
                    ),
                )
            )

        # Check 5: OHLCV has expected columns
        expected_columns = {"time", "open", "high", "low", "close", "volume"}
        actual_columns = set(ohlcv.columns) | {"time"}  # time is the index
        missing_columns = expected_columns - actual_columns

        if missing_columns:
            errors.append(
                ValidationError(
                    category="MISSING_COLUMNS",
                    message=f"OHLCV missing columns: {missing_columns}",
                    fix="Re-export OHLCV from TradingView with all required columns",
                )
            )

    # Check 6: Trades CSV has expected columns
    trades_path = data_dir / "trades.csv"
    if trades_path.exists():
        trades = pd.read_csv(trades_path)

        expected_trade_columns = {
            "Trade #",
            "Type",
            "Signal",
            "Date/Time",
            "Price",
            "Contracts",
            "Profit",
            "Cumulative",
            "Run-up",
            "Drawdown",
        }

        actual_trade_columns = set(trades.columns)
        missing_trade_columns = expected_trade_columns - actual_trade_columns

        if missing_trade_columns:
            errors.append(
                ValidationError(
                    category="MISSING_TRADE_COLUMNS",
                    message=f"Trades CSV missing columns: {missing_trade_columns}",
                    fix=(
                        "Re-export trades from TradingView. "
                        "Go to Strategy Tester → List of Trades → Export"
                    ),
                )
            )

        # Check 7: Date range matches metadata
        if "Date/Time" in trades.columns and "date_range" in metadata:
            trades["Date/Time"] = pd.to_datetime(trades["Date/Time"])
            actual_start = trades["Date/Time"].min()
            actual_end = trades["Date/Time"].max()

            expected_start = pd.to_datetime(metadata["date_range"]["start"])
            expected_end = pd.to_datetime(metadata["date_range"]["end"])

            # Allow trades to be slightly outside range (due to entry before validation period)  # noqa: E501
            if actual_start < expected_start - pd.Timedelta(days=30):
                errors.append(
                    ValidationError(
                        category="DATE_RANGE_MISMATCH",
                        message=(
                            f"Earliest trade ({actual_start.date()}) is more than "
                            f"30 days before metadata start ({expected_start.date()})"
                        ),
                        fix="Update metadata.json date_range or re-export trades",
                    )
                )

            if actual_end > expected_end + pd.Timedelta(days=1):
                errors.append(
                    ValidationError(
                        category="DATE_RANGE_MISMATCH",
                        message=(
                            f"Latest trade ({actual_end.date()}) is after "
                            f"metadata end ({expected_end.date()})"
                        ),
                        fix="Update metadata.json date_range or re-export trades",
                    )
                )

    # Check 8: Exit mechanisms match analyzer registry
    exit_mechanisms = metadata.get("exit_mechanisms", [])
    known_mechanisms = ["trailing_stop", "indicator_stop", "fixed_stop", "take_profit"]

    for mechanism in exit_mechanisms:
        if mechanism not in known_mechanisms:
            errors.append(
                ValidationError(
                    category="UNKNOWN_EXIT_MECHANISM",
                    message=f"Unknown exit mechanism: '{mechanism}'",
                    fix=(
                        f"Use one of: {known_mechanisms} or register a new analyzer "
                        f"in tests/validation/analyzers/"
                    ),
                )
            )

    # Check 9: Exit mechanism-specific fields
    if "trailing_stop" in exit_mechanisms:
        if "trailing_stop_pips" not in metadata:
            errors.append(
                ValidationError(
                    category="MISSING_METADATA",
                    message="trailing_stop requires 'trailing_stop_pips' in metadata",
                    fix="Add 'trailing_stop_pips': 0.0020 (or appropriate value) to metadata.json",  # noqa: E501
                )
            )

    if "indicator_stop" in exit_mechanisms:
        indicator_type = metadata.get("indicator_stop_type")
        if indicator_type is None:
            errors.append(
                ValidationError(
                    category="MISSING_METADATA",
                    message="indicator_stop requires 'indicator_stop_type' in metadata",
                    fix="Add 'indicator_stop_type': 'atr' (or other type) to metadata.json",  # noqa: E501
                )
            )
        if "indicator_stop_params" not in metadata:
            errors.append(
                ValidationError(
                    category="MISSING_METADATA",
                    message="indicator_stop requires 'indicator_stop_params' in metadata",  # noqa: E501
                    fix="Add 'indicator_stop_params': {'length': 14} to metadata.json",
                )
            )
        requires_multiplier = indicator_type == "atr"
        if requires_multiplier and "stop_distance_multiplier" not in metadata:
            errors.append(
                ValidationError(
                    category="MISSING_METADATA",
                    message="indicator_stop requires 'stop_distance_multiplier' in metadata",  # noqa: E501
                    fix="Add 'stop_distance_multiplier': 2.0 to metadata.json",
                )
            )

    return errors


def main():
    """Main validation entry point."""
    parser = argparse.ArgumentParser(
        description="Validate TradingView golden data exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strategy",
        help="Strategy to validate (e.g., ema_crossover/atr_stop)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all strategies",
    )

    args = parser.parse_args()

    if not args.strategy and not args.all:
        parser.error("Must specify either --strategy or --all")

    # Navigate to project root
    project_root = Path(__file__).parent.parent.parent

    # Get list of strategies to validate
    if args.all:
        strategies_dir = project_root / "data/dvc/golden/strategies"
        strategies = []
        for category_dir in strategies_dir.iterdir():
            if category_dir.is_dir():
                for strategy_dir in category_dir.iterdir():
                    if strategy_dir.is_dir():
                        relative_path = strategy_dir.relative_to(strategies_dir)
                        strategies.append(str(relative_path))
    else:
        strategies = [args.strategy]

    # Validate each strategy
    all_errors: Dict[str, List[ValidationError]] = {}
    for strategy in strategies:
        errors = validate_strategy(strategy, project_root)
        if errors:
            all_errors[strategy] = errors

    # Print summary
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}\n")

    if not all_errors:
        print("✅ All validations passed!\n")
        return 0
    else:
        total_errors = sum(len(errors) for errors in all_errors.values())
        print(
            f"❌ Found {total_errors} validation error(s) in {len(all_errors)} strategy(ies):\n"  # noqa: E501
        )

        for strategy, errors in all_errors.items():
            print(f"\n{strategy}:")
            for error in errors:
                print(f"  {error}\n")

        print(f"\n{'='*80}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Scaffold a new golden strategy test.

This script automates the creation of directory structure, template files,
and configuration for a new golden strategy test, reducing setup time from
5 minutes to under 2 minutes.

USAGE:
    # Trailing stop strategy
    poetry run python tests/validation/create_new_strategy_test.py \\
        --name "ema_crossover/30pip_trailing_stop" \\
        --exit-mechanism "trailing_stop" \\
        --trailing-stop-pips 30

    # ATR-based stop strategy
    poetry run python tests/validation/create_new_strategy_test.py \\
        --name "ema_crossover/2atr_stop" \\
        --exit-mechanism "indicator_stop" \\
        --indicator-type "atr" \\
        --indicator-params '{"length": 14}' \\
        --stop-multiplier 2.0

    # Trailing stop + take profit
    poetry run python tests/validation/create_new_strategy_test.py \\
        --name "ema_crossover/20pip_trailing_30pip_tp" \\
        --exit-mechanism "trailing_stop" \\
        --trailing-stop-pips 20 \\
        --take-profit-pips 30

EXIT CODES:
    0: Success
    1: Error (directory exists, invalid parameters, etc.)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def create_directories(strategy_name: str, project_root: Path) -> tuple[Path, Path]:
    """Create directory structure for new strategy.

    Args:
        strategy_name: Strategy name like "ema_crossover/atr_stop"
        project_root: Project root directory

    Returns:
        Tuple of (config_dir, data_dir) paths

    Raises:
        SystemExit: If directories already exist
    """
    config_dir = project_root / "configs/golden_strategies" / strategy_name
    data_dir = project_root / "data/dvc/golden/strategies" / strategy_name

    if config_dir.exists():
        print(f"❌ Error: Config directory already exists: {config_dir}")
        sys.exit(1)

    if data_dir.exists():
        print(f"❌ Error: Data directory already exists: {data_dir}")
        sys.exit(1)

    # Create directories
    config_dir.mkdir(parents=True, exist_ok=False)
    data_dir.mkdir(parents=True, exist_ok=False)

    print(f"✅ Created config directory: {config_dir}")
    print(f"✅ Created data directory: {data_dir}")

    return config_dir, data_dir


def create_metadata_json(
    data_dir: Path,
    strategy_name: str,
    exit_mechanism: str,
    trailing_stop_pips: Optional[int],
    take_profit_pips: Optional[int],
    indicator_type: Optional[str],
    indicator_params: Optional[Dict[str, Any]],
    stop_multiplier: Optional[float],
) -> None:
    """Create metadata.json file.

    Args:
        data_dir: Data directory path
        strategy_name: Strategy name
        exit_mechanism: Exit mechanism type
        trailing_stop_pips: Trailing stop pips (if applicable)
        take_profit_pips: Take profit pips (if applicable)
        indicator_type: Indicator type (if applicable)
        indicator_params: Indicator parameters (if applicable)
        stop_multiplier: Stop distance multiplier (if applicable)
    """
    metadata = {
        "dataset_type": "strategy",
        "strategy_name": strategy_name.replace("/", "_"),
        "tradingview_version": "TradingView 2025",
        "export_date": "TODO: Update after export",
        "timezone": "UTC (Reykjavik)",
        "date_range": {
            "start": "2023-01-01",
            "end": "2024-12-31",
        },
        "instrument": "OANDA:EURUSD",
        "timeframe": "1H",
        "position_size": 10000.0,
        "commission": 0.0,
        "initial_capital": 100000.0,
        "exit_mechanisms": [exit_mechanism],
    }

    # Add exit mechanism-specific fields
    if exit_mechanism == "trailing_stop":
        if trailing_stop_pips is None:
            raise ValueError("--trailing-stop-pips required for trailing_stop")
        metadata["trailing_stop_pips"] = trailing_stop_pips
        if take_profit_pips:
            metadata["take_profit_pips"] = take_profit_pips

    elif exit_mechanism == "indicator_stop":
        if not indicator_type:
            raise ValueError("--indicator-type required for indicator_stop")
        if not indicator_params:
            raise ValueError("--indicator-params required for indicator_stop")
        if stop_multiplier is None:
            raise ValueError("--stop-multiplier required for indicator_stop")

        metadata["indicator_stop_type"] = indicator_type
        metadata["indicator_stop_params"] = indicator_params
        metadata["stop_distance_multiplier"] = stop_multiplier

    # Add placeholder fields (to be updated after export)
    metadata.update(
        {
            "total_trades": 0,
            "closed_trades": 0,
            "open_trades": 0,
            "validation_range_total_trades": 0,
            "validation_range_closed_trades": 0,
            "net_profit": 0.0,
            "net_profit_percent": 0.0,
            "notes": (
                "TODO: Update after TradingView export. "
                "Include warmup period details and validation notes."
            ),
        }
    )

    metadata_path = data_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Created metadata.json: {metadata_path}")


def create_pinescript_template(
    config_dir: Path,
    strategy_name: str,
    exit_mechanism: str,
    indicator_type: Optional[str],
    stop_multiplier: Optional[float],
) -> None:
    """Create PineScript template file.

    Args:
        config_dir: Config directory path
        strategy_name: Strategy name
        exit_mechanism: Exit mechanism type
        indicator_type: Indicator type (if applicable)
        stop_multiplier: Stop multiplier (if applicable)
    """
    strategy_title = strategy_name.replace("/", " ").title() + " Golden"

    # Base strategy settings (mandatory)
    pinescript = f"""// @version=5
strategy("{strategy_title}",
         overlay=true,
         initial_capital=100000,
         default_qty_value=10000,
         default_qty_type=strategy.cash,
         commission_type=strategy.commission.percent,
         commission_value=0.0,
         pyramiding=1,
         process_orders_on_close=false,  // Execute next bar open
         calc_on_order_fills=false,       // Only calculate on bar close
         calc_on_every_tick=false)        // Not real-time

// MANDATORY: Include volume (even if unused)
plot(volume, title="Volume", display=display.none)

// ============================================================================
// INDICATORS
// ============================================================================

// Entry indicators
fast_length = input.int(10, "Fast EMA Length")
slow_length = input.int(20, "Slow EMA Length")
ema_fast = ta.ema(close, fast_length)
ema_slow = ta.ema(close, slow_length)

"""

    # Add exit mechanism-specific code
    if exit_mechanism == "trailing_stop":
        pinescript += """// Exit: Trailing Stop
trailing_stop_pips = input.int(20, "Trailing Stop (pips)")
trailing_stop_price = trailing_stop_pips * 0.0001  // Convert pips to price

// TODO: Add take profit if needed
// take_profit_pips = input.int(15, "Take Profit (pips)")
// take_profit_price = take_profit_pips * 0.0001

"""

    elif exit_mechanism == "indicator_stop" and indicator_type == "atr":
        pinescript += f"""// Exit: ATR-based Stop
atr_length = input.int(14, "ATR Length")
atr_multiplier = input.float({stop_multiplier or 2.0}, "ATR Multiplier")
atr = ta.atr(atr_length)

"""

    # Entry logic
    pinescript += """// ============================================================================  # noqa: E501
// ENTRY LOGIC
// ============================================================================

long_signal = ta.crossover(ema_fast, ema_slow)
short_signal = ta.crossunder(ema_fast, ema_slow)

if (long_signal)
    strategy.entry("Long", strategy.long)

if (short_signal)
    strategy.entry("Short", strategy.short)

"""

    # Exit logic
    if exit_mechanism == "trailing_stop":
        pinescript += """// ============================================================================  # noqa: E501
// EXIT LOGIC - Trailing Stop
// ============================================================================

if (strategy.position_size > 0)  // Long position
    strategy.exit("Exit Long", "Long", trail_offset=trailing_stop_price)

if (strategy.position_size < 0)  // Short position
    strategy.exit("Exit Short", "Short", trail_offset=trailing_stop_price)

// TODO: If using take profit, update strategy.exit() with profit= parameter

"""

    elif exit_mechanism == "indicator_stop" and indicator_type == "atr":
        pinescript += """// ============================================================================  # noqa: E501
// EXIT LOGIC - ATR-based Stop
// ============================================================================

var float stop_price = na

if (long_signal)
    stop_price := close - atr * atr_multiplier

if (short_signal)
    stop_price := close + atr * atr_multiplier

// Update stop based on current ATR
if (strategy.position_size > 0)  // Long position
    stop_price := close - atr * atr_multiplier
    strategy.exit("Exit Long", "Long", stop=stop_price)

if (strategy.position_size < 0)  // Short position
    stop_price := close + atr * atr_multiplier
    strategy.exit("Exit Short", "Short", stop=stop_price)

"""

    # Plotting
    pinescript += """// ============================================================================  # noqa: E501
// PLOTTING
// ============================================================================

plot(ema_fast, "Fast EMA", color=color.blue)
plot(ema_slow, "Slow EMA", color=color.red)

"""

    if exit_mechanism == "indicator_stop" and indicator_type == "atr":
        pinescript += 'plot(stop_price, "Stop Level", color=color.orange, style=plot.style_linebr)\n'  # noqa: E501

    pinescript_path = config_dir / "strategy.pine"
    with open(pinescript_path, "w") as f:
        f.write(pinescript)

    print(f"✅ Created PineScript template: {pinescript_path}")


def create_config_files(
    config_dir: Path,
    exit_mechanism: str,
    trailing_stop_pips: Optional[int],
    indicator_type: Optional[str],
    indicator_params: Optional[Dict[str, Any]],
    stop_multiplier: Optional[float],
) -> None:
    """Create strategy configuration YAML files.

    Args:
        config_dir: Config directory path
        exit_mechanism: Exit mechanism type
        trailing_stop_pips: Trailing stop pips (if applicable)
        indicator_type: Indicator type (if applicable)
        indicator_params: Indicator parameters (if applicable)
        stop_multiplier: Stop multiplier (if applicable)
    """
    # strategy.yaml
    strategy_yaml = """strategy:
  name: "ema_crossover"

  params:
    fast_length: 10
    slow_length: 20
"""

    if exit_mechanism == "indicator_stop" and indicator_type:
        params = indicator_params or {}
        strategy_yaml += f"    {indicator_type}_length: {params.get('length', 14)}\n"
        if stop_multiplier:
            strategy_yaml += f"    {indicator_type}_multiplier: {stop_multiplier}\n"

    strategy_path = config_dir / "strategy.yaml"
    with open(strategy_path, "w") as f:
        f.write(strategy_yaml)
    print(f"✅ Created strategy.yaml: {strategy_path}")

    # rem.yaml
    rem_yaml = "rem:\n"

    if exit_mechanism == "trailing_stop":
        rem_yaml += f"""  trailing_stop:
    pips: {trailing_stop_pips}
"""
    elif exit_mechanism == "indicator_stop":
        params = indicator_params or {}
        rem_yaml += f"""  stop_loss:
    type: "indicator"
    indicator: "{indicator_type}"
    params:
      length: {params.get('length', 14)}
    multiplier: {stop_multiplier}
    apply_on_entry: false  # Stop adjusts each bar
"""

    rem_path = config_dir / "rem.yaml"
    with open(rem_path, "w") as f:
        f.write(rem_yaml)
    print(f"✅ Created rem.yaml: {rem_path}")

    # run_config.yaml
    run_config_yaml = """warmup_bars: 100  # Enough for indicators to stabilize
execution_model: "next_bar_open"  # Match TradingView
exit_tie_break: "stop_then_tp"  # If both hit same bar

instrument:
  symbol: "EUR_USD"
  base_currency: "EUR"
  quote_currency: "USD"
  pip_location: -4
  contract_size: 100000

costs:
  spread_pips: 0.0
  commission_per_trade: 0.0
  slippage_pips: 0.0
"""

    run_config_path = config_dir / "run_config.yaml"
    with open(run_config_path, "w") as f:
        f.write(run_config_yaml)
    print(f"✅ Created run_config.yaml: {run_config_path}")


def print_next_steps(strategy_name: str, config_dir: Path, data_dir: Path) -> None:
    """Print checklist of remaining manual steps.

    Args:
        strategy_name: Strategy name
        config_dir: Config directory path
        data_dir: Data directory path
    """
    print(f"\n{'='*80}\n" f"✅ SCAFFOLD COMPLETE FOR: {strategy_name}\n" f"{'='*80}\n")

    print("📋 NEXT STEPS:\n")

    print("1. Review and customize PineScript:")
    print(f"   - Edit: {config_dir / 'strategy.pine'}")
    print("   - Verify mandatory settings (process_orders_on_close, etc.)")
    print("   - Ensure volume plot is included\n")

    print("2. Export from TradingView:")
    print("   - Load strategy in TradingView")
    print("   - Set chart to EUR/USD 1H")
    print("   - Set timezone to 'UTC (Reykjavik)'")
    print("   - Set date range: 2022-12-01 to 2024-12-31 (includes warmup)")
    print("   - Export trades: Strategy Tester → Export")
    print(f"     Save to: {data_dir / 'trades.csv'}")
    print("   - Export OHLCV: Chart → ... → Export chart data")
    print(f"     Save to: {data_dir / 'ohlcv.csv'}\n")

    print("3. Validate exported data:")
    print(
        f"   poetry run python tests/validation/validate_golden_data.py "
        f"--strategy {strategy_name}\n"
    )

    print("4. Update metadata.json:")
    print(f"   - Edit: {data_dir / 'metadata.json'}")
    print("   - Update export_date, total_trades, validation_range_total_trades")
    print("   - Add notes about warmup period and validation details\n")

    print("5. Generate platform golden trades:")
    print("   poetry run python tests/validation/generate_golden_trades.py\n")

    print("6. Add strategy to test suite:")
    print("   - Edit: tests/validation/test_export_exit_price_comparison.py")
    print(f"   - Add '{strategy_name}' to @pytest.mark.parametrize list")
    print("   - Do same for test_export_exit_time_comparison.py")
    print("   - Do same for test_strategy_validation.py\n")

    print("7. Run tests:")
    print(
        f"   poetry run pytest tests/validation/ -k '{strategy_name.split('/')[-1]}' -v\n"  # noqa: E501
    )

    print("8. If tests pass, add to DVC and commit:")
    print("   poetry run dvc add data/dvc/golden/strategies")
    print("   git add data/dvc/golden/strategies.dvc")
    print(f"   git add configs/golden_strategies/{strategy_name}")
    print(f"   git commit -m 'test: Add {strategy_name} golden validation'")
    print("   poetry run dvc push")
    print("   git push\n")

    print(f"{'='*80}")
    print("📖 For detailed instructions, see: tests/validation/README.md")
    print(f"{'='*80}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scaffold a new golden strategy test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Strategy name (e.g., 'ema_crossover/2atr_stop')",
    )

    parser.add_argument(
        "--exit-mechanism",
        required=True,
        choices=["trailing_stop", "indicator_stop"],
        help="Exit mechanism type",
    )

    # Trailing stop parameters
    parser.add_argument(
        "--trailing-stop-pips",
        type=int,
        help="Trailing stop distance in pips (required for trailing_stop)",
    )

    parser.add_argument(
        "--take-profit-pips",
        type=int,
        help="Take profit distance in pips (optional for trailing_stop)",
    )

    # Indicator stop parameters
    parser.add_argument(
        "--indicator-type",
        choices=["atr", "bollinger", "keltner", "donchian"],
        help="Indicator type (required for indicator_stop)",
    )

    parser.add_argument(
        "--indicator-params",
        type=json.loads,
        help="Indicator parameters as JSON (e.g., '{\"length\": 14}')",
    )

    parser.add_argument(
        "--stop-multiplier",
        type=float,
        help="Stop distance multiplier (required for indicator_stop)",
    )

    args = parser.parse_args()

    # Navigate to project root
    project_root = Path(__file__).parent.parent.parent

    print(f"\n🚀 Creating new golden strategy test: {args.name}\n")

    try:
        # Create directories
        config_dir, data_dir = create_directories(args.name, project_root)

        # Create metadata.json
        create_metadata_json(
            data_dir,
            args.name,
            args.exit_mechanism,
            args.trailing_stop_pips,
            args.take_profit_pips,
            args.indicator_type,
            args.indicator_params,
            args.stop_multiplier,
        )

        # Create PineScript template
        create_pinescript_template(
            config_dir,
            args.name,
            args.exit_mechanism,
            args.indicator_type,
            args.stop_multiplier,
        )

        # Create config files
        create_config_files(
            config_dir,
            args.exit_mechanism,
            args.trailing_stop_pips,
            args.indicator_type,
            args.indicator_params,
            args.stop_multiplier,
        )

        # Print next steps
        print_next_steps(args.name, config_dir, data_dir)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Trace minute-by-minute trailing stop processing for a specific trade.

This utility helps debug trailing stop exits by showing exactly how the stop
level evolves bar-by-bar and when/where the exit occurs.

Usage:
    python tools/trace_trailing_stop.py --trade-num 19
    python tools/trace_trailing_stop.py --trade-num 3 --verbose
"""

import argparse
from pathlib import Path

import pandas as pd


def load_1min_data(data_dir: Path | None = None) -> pd.DataFrame:
    """Load 1-minute OHLCV data."""
    if data_dir is None:
        data_dir = (
            Path(__file__).parent.parent
            / "data/dvc/golden/ohlcv/tradingview/full/eurusd"
        )

    data_path = data_dir / "eurusd_1min.csv"
    df = pd.read_csv(data_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    return df


def load_comparison_data(workspace_dir: Path | None = None) -> pd.DataFrame:
    """Load trade comparison CSV to get trade details."""
    if workspace_dir is None:
        workspace_dir = Path(__file__).parent.parent / "workspace"

    comparison_path = workspace_dir / "all_trades_comparison.csv"
    df = pd.read_csv(comparison_path)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["platform_exit_time"] = pd.to_datetime(df["platform_exit_time"])
    df["tv_exit_time"] = pd.to_datetime(df["tv_exit_time"])
    return df


def trace_trade(
    trade_num: int,
    trailing_offset: float = 0.0020,
    verbose: bool = False,
) -> None:
    """
    Trace the minute-by-minute processing of a specific trade.

    Args:
        trade_num: The trade number to trace
        trailing_offset: The trailing stop offset in price units
            (default 20 pips = 0.0020)
        verbose: If True, show all bars; if False, only show bars
            where stop changes or hits
    """
    # Load data
    df_1min = load_1min_data()
    df_comparison = load_comparison_data()

    # Get trade details
    trade = df_comparison[df_comparison["trade_num"] == trade_num].iloc[0]

    print(f"\n{'=' * 80}")
    print(f"TRADE #{trade_num} - {trade['direction']} POSITION")
    print(f"{'=' * 80}")
    print(f"Entry:  {trade['entry_time']} @ {trade['entry_price']:.5f}")
    print(
        f"Platform Exit: {trade['platform_exit_time']} @ "
        f"{trade['platform_exit_price']:.5f} "
        f"({trade['platform_exit_reason']})"
    )
    print(
        f"TV Exit: {trade['tv_exit_time']} @ "
        f"{trade['tv_exit_price']:.5f} "
        f"({trade['tv_exit_reason']})"
    )
    print(f"Platform P&L: {trade['platform_pnl_pips']:.1f} pips")
    print(f"TV P&L: {trade['tv_pnl_pips']:.1f} pips")
    print(f"{'=' * 80}\n")

    # Extract trade parameters
    entry_time = trade["entry_time"]
    entry_price = trade["entry_price"]
    side = trade["direction"].lower()
    exit_time_hourly = trade["platform_exit_time"]

    # Get all bars from entry through the end of the exit hour
    # (exit_time in comparison is hourly bar, but actual exit happens
    # on a specific minute)
    exit_hour_end = exit_time_hourly.floor("h") + pd.Timedelta(hours=1)
    bars = df_1min[entry_time:exit_hour_end]

    if len(bars) == 0:
        print("ERROR: No bars found between entry and exit time")
        return

    # Initialize tracking variables
    if side == "long":
        peak_or_trough = entry_price
        stop_level = entry_price - trailing_offset
        print(f"Initial peak: {peak_or_trough:.5f}")
        print(f"Initial stop: {stop_level:.5f}\n")
    else:  # short
        peak_or_trough = entry_price
        stop_level = entry_price + trailing_offset
        print(f"Initial trough: {peak_or_trough:.5f}")
        print(f"Initial stop: {stop_level:.5f}\n")

    # Process bars hour by hour
    current_hour = None

    for idx, bar in bars.iterrows():
        # Check if we've entered a new hour
        bar_hour = idx.floor("h")
        if bar_hour != current_hour:
            if current_hour is not None:
                print(f"\n{'-' * 80}")
            current_hour = bar_hour
            print(f"\n=== {bar_hour} HOUR ===")
            if side == "long":
                print(
                    f"Starting peak: {peak_or_trough:.5f}, " f"Stop: {stop_level:.5f}\n"
                )
            else:
                print(
                    f"Starting trough: {peak_or_trough:.5f}, "
                    f"Stop: {stop_level:.5f}\n"
                )

        # Check if stop hit
        if side == "long":
            stop_hit = bar["low"] <= stop_level
        else:  # short
            stop_hit = bar["high"] >= stop_level

        # Check if peak/trough improved
        if side == "long":
            improved = bar["high"] > peak_or_trough
            new_peak_or_trough = max(peak_or_trough, bar["high"])
            new_stop = max(
                entry_price - trailing_offset, new_peak_or_trough - trailing_offset
            )
        else:  # short
            improved = bar["low"] < peak_or_trough
            new_peak_or_trough = min(peak_or_trough, bar["low"])
            new_stop = min(
                entry_price + trailing_offset, new_peak_or_trough + trailing_offset
            )

        # Display output
        show_bar = verbose or improved or stop_hit

        if show_bar:
            print(f"{idx}")
            print(
                f"  O: {bar['open']:.5f}  H: {bar['high']:.5f}  "
                f"L: {bar['low']:.5f}  C: {bar['close']:.5f}"
            )

            if improved:
                if side == "long":
                    print(
                        f"  → Peak improved: {peak_or_trough:.5f} → "
                        f"{new_peak_or_trough:.5f}"
                    )
                else:
                    print(
                        f"  → Trough improved: {peak_or_trough:.5f} → "
                        f"{new_peak_or_trough:.5f}"
                    )
                print(f"  → Stop moved: {stop_level:.5f} → {new_stop:.5f}")
                peak_or_trough = new_peak_or_trough
                stop_level = new_stop

            if stop_hit:
                print(f"\n{'*' * 80}")
                print("*** STOP HIT! ***")
                if side == "long":
                    print(f"Bar low ({bar['low']:.5f}) <= Stop ({stop_level:.5f})")
                else:
                    print(f"Bar high ({bar['high']:.5f}) >= Stop ({stop_level:.5f})")
                print(f"Exit price: {stop_level:.5f}")
                print(f"{'*' * 80}\n")
                return

            if show_bar and not improved:
                print("  (no change)")

            print()

    print("\nNo stop hit detected in the data range.")


def main():
    parser = argparse.ArgumentParser(
        description="Trace minute-by-minute trailing stop processing for a trade"
    )
    parser.add_argument(
        "--trade-num", type=int, required=True, help="Trade number to analyze"
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0.0020,
        help="Trailing stop offset in price units (default: 0.0020 = 20 pips)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all bars, not just bars where stop changes or hits",
    )

    args = parser.parse_args()

    trace_trade(
        trade_num=args.trade_num,
        trailing_offset=args.offset,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()

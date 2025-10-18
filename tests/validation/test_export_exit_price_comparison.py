#!/usr/bin/env python3
"""Export exit price comparison to CSV for trailing stop validation."""

from pathlib import Path

import pandas as pd
import pytest

from tests.validation.golden_utils import load_and_validate_tradingview_trades
from tests.validation.test_strategy_validation import load_platform_trades
from tests.validation.trailing_stop_discrepancy_analyzer import (
    TrailingStopDiscrepancyAnalyzer,
)


@pytest.mark.strategy_name("ema_crossover/20pip_trailing_stop")
def test_export_exit_price_comparison(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
):
    """Export all trades with exit price comparison details to CSV.

    This test validates exit PRICES by categorizing all discrepancies.
    Unlike the exit time test, this one focuses on price differences even
    when exit times match.
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/20pip_trailing_stop",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Load TradingView trades
    strategy_dir = Path("data/dvc/golden/strategies/ema_crossover/20pip_trailing_stop")
    tv_trades_path = strategy_dir / "trades.csv"
    tv_df = load_and_validate_tradingview_trades(
        tv_trades_path, validation_range=date_range
    )

    # Convert platform trades to DataFrame
    platform_df = pd.DataFrame(platform_trades)

    # Sort both by entry time for alignment
    platform_df = platform_df.sort_values("entry_time").reset_index(drop=True)
    tv_df = tv_df.sort_values("entry_time").reset_index(drop=True)

    print(f"\nPlatform trades: {len(platform_df)}")
    print(f"TradingView trades: {len(tv_df)}")
    print(f"Total trades to compare: {min(len(platform_df), len(tv_df))}\n")

    # Use analyzer to categorize exit PRICE discrepancies
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
    )

    # Build lookup for categories by trade number
    category_lookup = {}
    for category_name, trades in categories.items():
        for trade in trades:
            category_lookup[trade["trade_num"]] = category_name

    # Build comparison data
    comparison_rows = []
    num_trades = min(len(platform_df), len(tv_df))

    for i in range(num_trades):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]

        # Get direction/side field
        p_direction = p_row.get("direction", p_row.get("side", "")).upper()

        # Calculate PnL in pips for platform (if not already present)
        if "pnl_pips" in p_row:
            platform_pnl_pips = p_row["pnl_pips"]
        else:
            # Calculate from entry/exit prices
            price_diff = p_row["exit_price"] - p_row["entry_price"]
            if p_direction == "SHORT":
                price_diff = -price_diff
            platform_pnl_pips = price_diff * 10000

        # Calculate PnL in pips for TradingView
        if "pnl_pips" in tv_row:
            tv_pnl_pips = tv_row["pnl_pips"]
        else:
            price_diff = tv_row["exit_price"] - tv_row["entry_price"]
            if tv_row["side"] == "short":
                price_diff = -price_diff
            tv_pnl_pips = price_diff * 10000

        # Calculate exit price difference
        exit_price_diff = abs(p_row["exit_price"] - tv_row["exit_price"])
        exit_price_diff_pips = exit_price_diff * 10000

        # Calculate PnL difference
        pnl_diff_pips = platform_pnl_pips - tv_pnl_pips

        # Check if exit prices match (within tolerance)
        exit_price_match = exit_price_diff < 0.00001

        # Determine if this trade FAILED exit PRICE validation
        exit_price_failed = not exit_price_match

        # Only categorize exit price failures
        trade_num = i + 1
        discrepancy_category = ""

        if exit_price_failed:
            # Check if same-bar entry/exit (explains failure)
            same_bar = (p_row["exit_time"] == p_row["entry_time"]) or (
                tv_row["exit_time"] == tv_row["entry_time"]
            )

            # Try to explain the failure
            if same_bar:
                discrepancy_category = "SAME_BAR_EXIT"
            else:
                # Check analyzer categories
                discrepancy_category = category_lookup.get(trade_num, "")

            # If still unexplained, mark as UNEXPLAINED
            if not discrepancy_category:
                discrepancy_category = "UNEXPLAINED"

        comparison_rows.append(
            {
                "trade_num": trade_num,
                "direction": p_direction,
                "entry_time": p_row["entry_time"],
                "entry_price": p_row["entry_price"],
                "platform_exit_time": p_row["exit_time"],
                "platform_exit_price": p_row["exit_price"],
                "platform_exit_reason": p_row["exit_reason"],
                "platform_pnl_pips": platform_pnl_pips,
                "tv_exit_time": tv_row["exit_time"],
                "tv_exit_price": tv_row["exit_price"],
                "tv_exit_reason": tv_row.get("exit_reason", ""),
                "tv_pnl_pips": tv_pnl_pips,
                "exit_price_match": exit_price_match,
                "exit_price_diff_pips": exit_price_diff_pips,
                "pnl_diff_pips": pnl_diff_pips,
                # Failure explanation (only populated for failed trades)
                "failure_explanation": discrepancy_category,
            }
        )

    # Create DataFrame and save to CSV
    comparison_df = pd.DataFrame(comparison_rows)
    output_path = Path("workspace/exit_price_comparison.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(output_path, index=False)

    print(f"✓ Exit price comparison exported to: {output_path}")

    # Print summary statistics
    total_trades = len(comparison_df)
    price_matches = comparison_df["exit_price_match"].sum()
    price_failures = total_trades - price_matches

    print(f"\n{'='*80}")
    print("EXIT PRICE VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total trades: {total_trades}")
    print(f"Exit prices match: {price_matches}")
    print(f"Exit price failures: {price_failures}")

    if price_failures > 0:
        print("\nFailed trades breakdown:")
        failure_counts = (
            comparison_df[comparison_df["failure_explanation"] != ""]
            .groupby("failure_explanation")
            .size()
        )
        for category, count in failure_counts.items():
            print(f"  {category}: {count}")

        # Check for unexplained
        unexplained = failure_counts.get("UNEXPLAINED", 0)
        if unexplained > 0:
            print(f"\n⚠ WARNING: {unexplained} UNEXPLAINED exit price discrepancies!")
            print("These need investigation.")
        else:
            print(f"\n✓ All {price_failures} exit price failures are explained!")

    print(f"{'='*80}\n")

    # The test passes as long as we generated the file
    # Actual validation happens in test_strategy_validation.py
    assert output_path.exists()

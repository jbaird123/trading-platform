#!/usr/bin/env python3
"""Export all trades comparison to CSV."""

from pathlib import Path

import pandas as pd
import pytest

from tests.validation.analyzers.trailing_stop import (
    TrailingStopDiscrepancyAnalyzer,
)
from tests.validation.golden_utils import load_and_validate_tradingview_trades
from tests.validation.test_strategy_validation import (
    KNOWN_EDGE_CASES,
)


@pytest.mark.strategy_name("ema_crossover/20pip_trailing_stop")
def test_export_all_trades_comparison(
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Export all trades with full comparison details to CSV."""
    date_range = golden_metadata.get("date_range")

    # Use session-scoped platform trades fixture (already filtered to validation range)
    platform_trades = platform_trades_20pip_trailing_stop

    # Load TradingView trades using the correct golden_utils function
    # Note: The fixture gives us raw CSV, we need to parse and filter it
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

    # Debug: Check if trade #18 exists in TV dataframe
    print("\n=== DEBUG: Looking for Trade #18 ===")
    if "trade_num" in tv_df.columns:
        trade_18 = tv_df[tv_df["trade_num"] == 18]
        if len(trade_18) > 0:
            print("Found Trade #18 in tv_df:")
            t18 = trade_18.iloc[0]
            print(f"  Entry: {t18['entry_time']} @ {t18['entry_price']}")
            print(f"  Exit: {t18['exit_time']} @ {t18['exit_price']}")
            print(f"  Index in DataFrame: {trade_18.index[0]}")
        else:
            print("Trade #18 NOT FOUND in tv_df!")
            print(
                f"Available trade_nums: {sorted(tv_df['trade_num'].unique())[:20]}..."
            )

    # Check trade #6 by index
    print("\n=== DEBUG: Trade at index 5 (displayed as #6) ===")
    if len(platform_df) >= 6:
        p6 = platform_df.iloc[5]  # 0-indexed
        print("Platform trade at index 5:")
        print(f"  Entry: {p6['entry_time']} @ {p6['entry_price']}")
        print(f"  Exit: {p6['exit_time']} @ {p6['exit_price']}")
    if len(tv_df) >= 6:
        tv6 = tv_df.iloc[5]  # 0-indexed
        print("TradingView trade at index 5:")
        print(f"  Entry: {tv6['entry_time']} @ {tv6['entry_price']}")
        print(f"  Exit: {tv6['exit_time']} @ {tv6['exit_price']}")
        if "trade_num" in tv6:
            print(f"  Original Trade #: {tv6['trade_num']}")
    print("======================\n")

    # Ensure both have the same number of trades
    if len(platform_df) != len(tv_df):
        print("⚠ WARNING: Trade count mismatch!")
        print(f"  Platform: {len(platform_df)}")
        print(f"  TradingView: {len(tv_df)}")
        print(f"  Will only compare first {min(len(platform_df), len(tv_df))} trades\n")

    # Use analyzer to categorize discrepancies
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
    )

    # Get known edge cases
    strategy_edge_cases = KNOWN_EDGE_CASES.get("ema_crossover/20pip_trailing_stop", {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Build category lookup by trade number
    category_lookup = {}

    # Add analyzer categories
    for category_name in analyzer.KNOWN_ACCEPTABLE_CATEGORIES:
        for trade in categories.get(category_name, []):
            category_lookup[trade["trade_num"]] = category_name

    # Add known edge cases
    for edge_case in known_exit_time_edge_cases:
        trade_num = edge_case["trade_index"] + 1  # Convert to 1-indexed
        category_lookup[trade_num] = "KNOWN_EDGE_CASE"

    # Create comparison DataFrame
    comparisons = []

    # Only compare up to the minimum length
    num_trades = min(len(platform_df), len(tv_df))
    for i in range(num_trades):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]

        # Calculate P&L in pips for both
        # P&L = (exit_price - entry_price) * direction_multiplier * 10000
        # For LONG: positive if exit > entry (profit)
        # For SHORT: positive if exit < entry (profit)
        direction_multiplier = 1 if p_row["side"] == "long" else -1
        platform_pnl_pips = (
            (p_row["exit_price"] - p_row["entry_price"]) * direction_multiplier * 10000
        )
        tv_pnl_pips = (
            (tv_row["exit_price"] - tv_row["entry_price"])
            * direction_multiplier
            * 10000
        )

        # Calculate differences
        exit_time_match = p_row["exit_time"] == tv_row["exit_time"]
        exit_price_diff = abs(p_row["exit_price"] - tv_row["exit_price"]) * 10000
        pnl_diff = platform_pnl_pips - tv_pnl_pips

        # Determine if this trade FAILED exit TIME validation
        # (We're only testing exit times, not prices)
        exit_time_failed = not exit_time_match

        # Only categorize exit time failures
        trade_num = i + 1
        discrepancy_category = ""

        if exit_time_failed:
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

        comparison = {
            "trade_num": trade_num,
            "direction": p_row["side"].upper(),
            # Entry
            "entry_time": str(p_row["entry_time"]),
            "entry_price": p_row["entry_price"],
            # Platform exit
            "platform_exit_time": str(p_row["exit_time"]),
            "platform_exit_price": p_row["exit_price"],
            "platform_exit_reason": p_row.get("exit_reason", "N/A"),
            "platform_pnl_pips": platform_pnl_pips,
            # TradingView exit
            "tv_exit_time": str(tv_row["exit_time"]),
            "tv_exit_price": tv_row["exit_price"],
            "tv_exit_reason": tv_row.get("exit_reason", "N/A"),
            "tv_pnl_pips": tv_pnl_pips,
            # Validation results
            "exit_time_match": exit_time_match,
            "exit_price_diff_pips": exit_price_diff,
            "pnl_diff_pips": pnl_diff,
            # Failure explanation (only populated for failed trades)
            "failure_explanation": discrepancy_category,
        }

        comparisons.append(comparison)

    # Create DataFrame
    df = pd.DataFrame(comparisons)

    # Save to CSV
    output_path = Path("workspace/all_trades_comparison.csv")
    df.to_csv(output_path, index=False)
    print(f"✓ Saved all trades comparison to: {output_path}\n")

    # Print summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    total = len(df)
    exit_time_matches = df["exit_time_match"].sum()
    exit_time_mismatches = total - exit_time_matches

    print(f"Total trades: {total}")
    print(f"Exit time matches: {exit_time_matches}")
    print(f"Exit time mismatches: {exit_time_mismatches}")
    print()

    # Failure explanation breakdown
    print("Validation Failures by Category:")
    failure_counts = df[df["failure_explanation"] != ""][
        "failure_explanation"
    ].value_counts()
    for category, count in failure_counts.items():
        print(f"  - {category}: {count}")

    # Count trades that passed validation
    passed_validation = (df["failure_explanation"] == "").sum()
    print(f"\nPassed validation (perfect match): {passed_validation}")
    explained = len(df) - passed_validation - failure_counts.get("UNEXPLAINED", 0)
    print(f"Failed validation (explained): {explained}")
    unexplained = failure_counts.get("UNEXPLAINED", 0)
    if unexplained > 0:
        print(f"Failed validation (UNEXPLAINED): {unexplained} ⚠️")
    print()

    # Exit price differences
    price_diffs = df["exit_price_diff_pips"]
    print("Exit price differences (pips):")
    print(f"  Min:  {price_diffs.min():.2f}")
    print(f"  Max:  {price_diffs.max():.2f}")
    print(f"  Mean: {price_diffs.mean():.2f}")
    print(f"  Median: {price_diffs.median():.2f}")
    print()

    # P&L differences
    pnl_diffs = df["pnl_diff_pips"].abs()
    print("P&L differences (absolute, pips):")
    print(f"  Min:  {pnl_diffs.min():.2f}")
    print(f"  Max:  {pnl_diffs.max():.2f}")
    print(f"  Mean: {pnl_diffs.mean():.2f}")
    print(f"  Median: {pnl_diffs.median():.2f}")
    print()

    # Show first 10 unexplained failures
    unexplained_df = df[df["failure_explanation"] == "UNEXPLAINED"]
    if len(unexplained_df) > 0:
        print("=" * 80)
        print("UNEXPLAINED VALIDATION FAILURES (Require Investigation)")
        print("=" * 80)
        print()

        for idx, row in unexplained_df.head(10).iterrows():
            print(f"Trade #{row['trade_num']} ({row['direction']})")
            print(f"  Entry:    {row['entry_time']} @ {row['entry_price']:.5f}")
            print()
            print(
                f"  Platform: {row['platform_exit_time']} @ "
                f"{row['platform_exit_price']:.5f}"
            )
            print(
                f"            Reason: {row['platform_exit_reason']}, "
                f"P&L: {row['platform_pnl_pips']:.1f} pips"
            )
            print()
            print(
                f"  TradingView: {row['tv_exit_time']} @ " f"{row['tv_exit_price']:.5f}"
            )
            print(
                f"               Reason: {row['tv_exit_reason']}, "
                f"P&L: {row['tv_pnl_pips']:.1f} pips"
            )
            print()
            print(
                f"  Differences: Price: {row['exit_price_diff_pips']:.2f} pips, "
                f"P&L: {row['pnl_diff_pips']:+.1f} pips"
            )
            print("-" * 80)
            print()


@pytest.mark.strategy_name("ema_crossover/20pip_trailing_stop_15pip_tp")
def test_export_all_trades_comparison_20pip_15pip(
    tradingview_trades,
    tradingview_ohlcv,
    golden_metadata,
    platform_trades_20pip_trailing_stop_15pip_tp,
):
    """Export all trades with full comparison details to CSV."""
    date_range = golden_metadata.get("date_range")

    # Use session-scoped platform trades fixture (already filtered to validation range)
    platform_trades = platform_trades_20pip_trailing_stop_15pip_tp

    # Load TradingView trades using the correct golden_utils function
    # Note: The fixture gives us raw CSV, we need to parse and filter it
    strategy_dir = Path(
        "data/dvc/golden/strategies/ema_crossover/20pip_trailing_stop_15pip_tp"
    )
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

    # Debug: Check if trade #18 exists in TV dataframe
    print("\n=== DEBUG: Looking for Trade #18 ===")
    if "trade_num" in tv_df.columns:
        trade_18 = tv_df[tv_df["trade_num"] == 18]
        if len(trade_18) > 0:
            print("Found Trade #18 in tv_df:")
            t18 = trade_18.iloc[0]
            print(f"  Entry: {t18['entry_time']} @ {t18['entry_price']}")
            print(f"  Exit: {t18['exit_time']} @ {t18['exit_price']}")
            print(f"  Index in DataFrame: {trade_18.index[0]}")
        else:
            print("Trade #18 NOT FOUND in tv_df!")
            print(
                f"Available trade_nums: {sorted(tv_df['trade_num'].unique())[:20]}..."
            )

    # Check trade #6 by index
    print("\n=== DEBUG: Trade at index 5 (displayed as #6) ===")
    if len(platform_df) >= 6:
        p6 = platform_df.iloc[5]  # 0-indexed
        print("Platform trade at index 5:")
        print(f"  Entry: {p6['entry_time']} @ {p6['entry_price']}")
        print(f"  Exit: {p6['exit_time']} @ {p6['exit_price']}")
    if len(tv_df) >= 6:
        tv6 = tv_df.iloc[5]  # 0-indexed
        print("TradingView trade at index 5:")
        print(f"  Entry: {tv6['entry_time']} @ {tv6['entry_price']}")
        print(f"  Exit: {tv6['exit_time']} @ {tv6['exit_price']}")
        if "trade_num" in tv6:
            print(f"  Original Trade #: {tv6['trade_num']}")
    print("======================\n")

    # Ensure both have the same number of trades
    if len(platform_df) != len(tv_df):
        print("⚠ WARNING: Trade count mismatch!")
        print(f"  Platform: {len(platform_df)}")
        print(f"  TradingView: {len(tv_df)}")
        print(f"  Will only compare first {min(len(platform_df), len(tv_df))} trades\n")

    # Use analyzer to categorize discrepancies
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
    )

    # Get known edge cases
    strategy_edge_cases = KNOWN_EDGE_CASES.get(
        "ema_crossover/20pip_trailing_stop_15pip_tp", {}
    )
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Build category lookup by trade number
    category_lookup = {}

    # Add analyzer categories
    for category_name in analyzer.KNOWN_ACCEPTABLE_CATEGORIES:
        for trade in categories.get(category_name, []):
            category_lookup[trade["trade_num"]] = category_name

    # Add known edge cases
    for edge_case in known_exit_time_edge_cases:
        trade_num = edge_case["trade_index"] + 1  # Convert to 1-indexed
        category_lookup[trade_num] = "KNOWN_EDGE_CASE"

    # Create comparison DataFrame
    comparisons = []

    # Only compare up to the minimum length
    num_trades = min(len(platform_df), len(tv_df))
    for i in range(num_trades):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]

        # Calculate P&L in pips for both
        # P&L = (exit_price - entry_price) * direction_multiplier * 10000
        # For LONG: positive if exit > entry (profit)
        # For SHORT: positive if exit < entry (profit)
        direction_multiplier = 1 if p_row["side"] == "long" else -1
        platform_pnl_pips = (
            (p_row["exit_price"] - p_row["entry_price"]) * direction_multiplier * 10000
        )
        tv_pnl_pips = (
            (tv_row["exit_price"] - tv_row["entry_price"])
            * direction_multiplier
            * 10000
        )

        # Calculate differences
        exit_time_match = p_row["exit_time"] == tv_row["exit_time"]
        exit_price_diff = abs(p_row["exit_price"] - tv_row["exit_price"]) * 10000
        pnl_diff = platform_pnl_pips - tv_pnl_pips

        # Determine if this trade FAILED exit TIME validation
        # (We're only testing exit times, not prices)
        exit_time_failed = not exit_time_match

        # Only categorize exit time failures
        trade_num = i + 1
        discrepancy_category = ""

        if exit_time_failed:
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

        comparison = {
            "trade_num": trade_num,
            "direction": p_row["side"].upper(),
            # Entry
            "entry_time": str(p_row["entry_time"]),
            "entry_price": p_row["entry_price"],
            # Platform exit
            "platform_exit_time": str(p_row["exit_time"]),
            "platform_exit_price": p_row["exit_price"],
            "platform_exit_reason": p_row.get("exit_reason", "N/A"),
            "platform_pnl_pips": platform_pnl_pips,
            # TradingView exit
            "tv_exit_time": str(tv_row["exit_time"]),
            "tv_exit_price": tv_row["exit_price"],
            "tv_exit_reason": tv_row.get("exit_reason", "N/A"),
            "tv_pnl_pips": tv_pnl_pips,
            # Validation results
            "exit_time_match": exit_time_match,
            "exit_price_diff_pips": exit_price_diff,
            "pnl_diff_pips": pnl_diff,
            # Failure explanation (only populated for failed trades)
            "failure_explanation": discrepancy_category,
        }

        comparisons.append(comparison)

    # Create DataFrame
    df = pd.DataFrame(comparisons)

    # Save to CSV
    output_path = Path("workspace/all_trades_comparison.csv")
    df.to_csv(output_path, index=False)
    print(f"✓ Saved all trades comparison to: {output_path}\n")

    # Print summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    total = len(df)
    exit_time_matches = df["exit_time_match"].sum()
    exit_time_mismatches = total - exit_time_matches

    print(f"Total trades: {total}")
    print(f"Exit time matches: {exit_time_matches}")
    print(f"Exit time mismatches: {exit_time_mismatches}")
    print()

    # Failure explanation breakdown
    print("Validation Failures by Category:")
    failure_counts = df[df["failure_explanation"] != ""][
        "failure_explanation"
    ].value_counts()
    for category, count in failure_counts.items():
        print(f"  - {category}: {count}")

    # Count trades that passed validation
    passed_validation = (df["failure_explanation"] == "").sum()
    print(f"\nPassed validation (perfect match): {passed_validation}")
    explained = len(df) - passed_validation - failure_counts.get("UNEXPLAINED", 0)
    print(f"Failed validation (explained): {explained}")
    unexplained = failure_counts.get("UNEXPLAINED", 0)
    if unexplained > 0:
        print(f"Failed validation (UNEXPLAINED): {unexplained} ⚠️")
    print()

    # Exit price differences
    price_diffs = df["exit_price_diff_pips"]
    print("Exit price differences (pips):")
    print(f"  Min:  {price_diffs.min():.2f}")
    print(f"  Max:  {price_diffs.max():.2f}")
    print(f"  Mean: {price_diffs.mean():.2f}")
    print(f"  Median: {price_diffs.median():.2f}")
    print()

    # P&L differences
    pnl_diffs = df["pnl_diff_pips"].abs()
    print("P&L differences (absolute, pips):")
    print(f"  Min:  {pnl_diffs.min():.2f}")
    print(f"  Max:  {pnl_diffs.max():.2f}")
    print(f"  Mean: {pnl_diffs.mean():.2f}")
    print(f"  Median: {pnl_diffs.median():.2f}")
    print()

    # Show first 10 unexplained failures
    unexplained_df = df[df["failure_explanation"] == "UNEXPLAINED"]
    if len(unexplained_df) > 0:
        print("=" * 80)
        print("UNEXPLAINED VALIDATION FAILURES (Require Investigation)")
        print("=" * 80)
        print()

        for idx, row in unexplained_df.head(10).iterrows():
            print(f"Trade #{row['trade_num']} ({row['direction']})")
            print(f"  Entry:    {row['entry_time']} @ {row['entry_price']:.5f}")
            print()
            print(
                f"  Platform: {row['platform_exit_time']} @ "
                f"{row['platform_exit_price']:.5f}"
            )
            print(
                f"            Reason: {row['platform_exit_reason']}, "
                f"P&L: {row['platform_pnl_pips']:.1f} pips"
            )
            print()
            print(
                f"  TradingView: {row['tv_exit_time']} @ " f"{row['tv_exit_price']:.5f}"
            )
            print(
                f"               Reason: {row['tv_exit_reason']}, "
                f"P&L: {row['tv_pnl_pips']:.1f} pips"
            )
            print()
            print(
                f"  Differences: Price: {row['exit_price_diff_pips']:.2f} pips, "
                f"P&L: {row['pnl_diff_pips']:+.1f} pips"
            )
            print("-" * 80)
            print()

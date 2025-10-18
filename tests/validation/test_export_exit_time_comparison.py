#!/usr/bin/env python3
"""Export exit time comparison to CSV for trailing stop validation."""

from pathlib import Path

import pandas as pd
import pytest

from tests.validation.golden_utils import load_and_validate_tradingview_trades
from tests.validation.test_strategy_validation import (
    KNOWN_EDGE_CASES,
    load_platform_trades,
)
from tests.validation.trailing_stop_discrepancy_analyzer import (
    TrailingStopDiscrepancyAnalyzer,
)


@pytest.mark.strategy_name("ema_crossover/20pip_trailing_stop")
def test_export_exit_time_comparison(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
):
    """Export all trades with exit time comparison details to CSV.

    This test validates exit TIMES by categorizing all discrepancies.
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

    # Get known edge cases for exit time mismatches
    strategy_edge_cases = KNOWN_EDGE_CASES.get("ema_crossover/20pip_trailing_stop", {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Build set of trade indices for known edge cases
    known_edge_case_indices = {ec["trade_index"] for ec in known_exit_time_edge_cases}

    print(f"Known exit time edge cases: {len(known_exit_time_edge_cases)}")
    if known_exit_time_edge_cases:
        print(
            "  Trade indices:",
            sorted([ec["trade_index"] + 1 for ec in known_exit_time_edge_cases]),
        )
    print()

    # Use analyzer to categorize discrepancies (provides MFE-based categorization)
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0020,  # 20 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    # Build lookup for categories and explanations by trade number
    category_lookup = {}
    explanation_lookup = {}
    for category_name, trades in categories.items():
        for trade in trades:
            trade_num = trade["trade_num"]
            category_lookup[trade_num] = category_name
            explanation_lookup[trade_num] = trade.get("explanation", "")

    # Build comparison rows
    comparison_rows = []
    for i in range(min(len(platform_df), len(tv_df))):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]
        trade_num = i + 1

        # Extract times
        platform_exit_time = p_row["exit_time"]
        tv_exit_time = tv_row["exit_time"]

        # Check if times match
        exit_time_match = platform_exit_time == tv_exit_time

        # Determine time mismatch category
        time_mismatch_category = ""
        time_mismatch_explanation = ""

        if not exit_time_match:
            # Check if this is a known edge case
            trade_index = i  # 0-indexed
            if trade_index in known_edge_case_indices:
                # Find the edge case details
                edge_case = next(
                    (
                        ec
                        for ec in known_exit_time_edge_cases
                        if ec["trade_index"] == trade_index
                    ),
                    None,
                )
                if edge_case:
                    time_mismatch_category = "KNOWN_EDGE_CASE"
                    time_mismatch_explanation = edge_case["description"]
            else:
                # Check if explained by analyzer
                # Only certain categories explain exit TIME mismatches:
                exit_time_categories = [
                    "SAME_BAR_EXIT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
                ]

                analyzer_category = category_lookup.get(trade_num, "")
                if analyzer_category in exit_time_categories:
                    time_mismatch_category = analyzer_category
                    time_mismatch_explanation = explanation_lookup.get(trade_num, "")
                else:
                    # Unexplained time mismatch
                    time_mismatch_category = "UNEXPLAINED"
                    time_mismatch_explanation = (
                        "Exit time discrepancy requires investigation."
                    )

        comparison_rows.append(
            {
                "trade_num": trade_num,
                "direction": p_row["side"].upper(),
                "entry_time": str(p_row["entry_time"]),
                "platform_exit_time": str(platform_exit_time),
                "tv_exit_time": str(tv_exit_time),
                "exit_time_match": exit_time_match,
                "time_mismatch_category": time_mismatch_category,
                "time_mismatch_explanation": time_mismatch_explanation,
            }
        )

    # Create DataFrame and save to CSV
    comparison_df = pd.DataFrame(comparison_rows)
    output_path = Path("workspace/exit_time_comparison.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(output_path, index=False)

    print(f"✓ Exit time comparison exported to: {output_path}")

    # Verify comparison file hash matches golden reference
    from tests.validation.test_strategy_validation import verify_golden_comparison_hash

    verify_golden_comparison_hash(
        "ema_crossover/20pip_trailing_stop",
        output_path,
        golden_filename="exit_time_comparison_golden.csv",
    )

    # Print summary statistics
    total_trades = len(comparison_df)
    time_matches = comparison_df["exit_time_match"].sum()
    time_mismatches = total_trades - time_matches

    print(f"\n{'='*80}")
    print("EXIT TIME VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total trades: {total_trades}")
    print(f"Exit times match: {time_matches}")
    print(f"Exit times mismatch: {time_mismatches}")

    if time_mismatches > 0:
        print("\nTime Mismatch Categories:")
        category_counts = comparison_df[~comparison_df["exit_time_match"]][
            "time_mismatch_category"
        ].value_counts()
        for category, count in category_counts.items():
            print(f"  {category}: {count}")

    print(f"{'='*80}\n")

    # Assert all time mismatches are explained
    unexplained = comparison_df[
        comparison_df["time_mismatch_category"] == "UNEXPLAINED"
    ]

    assert len(unexplained) == 0, (
        f"Found {len(unexplained)} UNEXPLAINED exit time mismatches!\n"
        f"All time discrepancies must be categorized and explained.\n"
        f"See {output_path} for details."
    )


@pytest.mark.strategy_name("ema_crossover/30pip_trailing_stop_20pip_tp")
def test_export_exit_time_comparison_30pip(
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
):
    """Export all trades with exit time comparison details to CSV.

    This test validates exit TIMES by categorizing all discrepancies.
    """
    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name="ema_crossover/30pip_trailing_stop_20pip_tp",
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
    )

    # Load TradingView trades
    strategy_dir = Path(
        "data/dvc/golden/strategies/ema_crossover/30pip_trailing_stop_20pip_tp"
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

    # Get known edge cases for exit time mismatches
    strategy_edge_cases = KNOWN_EDGE_CASES.get(
        "ema_crossover/30pip_trailing_stop_20pip_tp", {}
    )
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    # Build set of trade indices for known edge cases
    known_edge_case_indices = {ec["trade_index"] for ec in known_exit_time_edge_cases}

    print(f"Known exit time edge cases: {len(known_exit_time_edge_cases)}")
    if known_exit_time_edge_cases:
        print(
            "  Trade indices:",
            sorted([ec["trade_index"] + 1 for ec in known_exit_time_edge_cases]),
        )
    print()

    # Use analyzer to categorize discrepancies (provides MFE-based categorization)
    analyzer = TrailingStopDiscrepancyAnalyzer(
        trailing_stop_pips=0.0030,  # 30 pips
        tolerance=0.00001,
    )

    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    # Build lookup for categories and explanations by trade number
    category_lookup = {}
    explanation_lookup = {}
    for category_name, trades in categories.items():
        for trade in trades:
            trade_num = trade["trade_num"]
            category_lookup[trade_num] = category_name
            explanation_lookup[trade_num] = trade.get("explanation", "")

    # Build comparison rows
    comparison_rows = []
    for i in range(min(len(platform_df), len(tv_df))):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]
        trade_num = i + 1

        # Extract times
        platform_exit_time = p_row["exit_time"]
        tv_exit_time = tv_row["exit_time"]

        # Check if times match
        exit_time_match = platform_exit_time == tv_exit_time

        # Determine time mismatch category
        time_mismatch_category = ""
        time_mismatch_explanation = ""

        if not exit_time_match:
            # Check if this is a known edge case
            trade_index = i  # 0-indexed
            if trade_index in known_edge_case_indices:
                # Find the edge case details
                edge_case = next(
                    (
                        ec
                        for ec in known_exit_time_edge_cases
                        if ec["trade_index"] == trade_index
                    ),
                    None,
                )
                if edge_case:
                    time_mismatch_category = "KNOWN_EDGE_CASE"
                    time_mismatch_explanation = edge_case["description"]
            else:
                # Check if explained by analyzer
                # Only certain categories explain exit TIME mismatches:
                exit_time_categories = [
                    "SAME_BAR_EXIT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
                    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
                ]

                analyzer_category = category_lookup.get(trade_num, "")
                if analyzer_category in exit_time_categories:
                    time_mismatch_category = analyzer_category
                    time_mismatch_explanation = explanation_lookup.get(trade_num, "")
                else:
                    # Unexplained time mismatch
                    time_mismatch_category = "UNEXPLAINED"
                    time_mismatch_explanation = (
                        "Exit time discrepancy requires investigation."
                    )

        comparison_rows.append(
            {
                "trade_num": trade_num,
                "direction": p_row["side"].upper(),
                "entry_time": str(p_row["entry_time"]),
                "platform_exit_time": str(platform_exit_time),
                "tv_exit_time": str(tv_exit_time),
                "exit_time_match": exit_time_match,
                "time_mismatch_category": time_mismatch_category,
                "time_mismatch_explanation": time_mismatch_explanation,
            }
        )

    # Create DataFrame and save to CSV
    comparison_df = pd.DataFrame(comparison_rows)
    output_path = Path("workspace/exit_time_comparison.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(output_path, index=False)

    print(f"✓ Exit time comparison exported to: {output_path}")

    # Verify comparison file hash matches golden reference
    from tests.validation.test_strategy_validation import verify_golden_comparison_hash

    verify_golden_comparison_hash(
        "ema_crossover/30pip_trailing_stop_20pip_tp",
        output_path,
        golden_filename="exit_time_comparison_golden.csv",
    )

    # Print summary statistics
    total_trades = len(comparison_df)
    time_matches = comparison_df["exit_time_match"].sum()
    time_mismatches = total_trades - time_matches

    print(f"\n{'='*80}")
    print("EXIT TIME VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total trades: {total_trades}")
    print(f"Exit times match: {time_matches}")
    print(f"Exit times mismatch: {time_mismatches}")

    if time_mismatches > 0:
        print("\nTime Mismatch Categories:")
        category_counts = comparison_df[~comparison_df["exit_time_match"]][
            "time_mismatch_category"
        ].value_counts()
        for category, count in category_counts.items():
            print(f"  {category}: {count}")

    print(f"{'='*80}\n")

    # Assert all time mismatches are explained
    unexplained = comparison_df[
        comparison_df["time_mismatch_category"] == "UNEXPLAINED"
    ]

    assert len(unexplained) == 0, (
        f"Found {len(unexplained)} UNEXPLAINED exit time mismatches!\n"
        f"All time discrepancies must be categorized and explained.\n"
        f"See {output_path} for details."
    )

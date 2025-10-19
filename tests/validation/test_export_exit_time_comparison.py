#!/usr/bin/env python3
"""Export exit time comparison to CSV for trailing stop validation.

This module has been refactored to use shared utility functions and
parametrization to eliminate code duplication.
"""

from pathlib import Path

import pytest

from tests.validation.analyzers import create_analyzer_for_strategy
from tests.validation.comparison_export import export_comparison_csv
from tests.validation.comparison_utils import build_category_lookup
from tests.validation.golden_utils import load_and_prepare_trade_data
from tests.validation.test_strategy_validation import (
    KNOWN_EDGE_CASES,
    load_platform_trades,
    verify_golden_comparison_hash,
)

# Define allowed categories that explain exit TIME mismatches
EXIT_TIME_CATEGORIES = [
    "SAME_BAR_EXIT",
    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
    "PLATFORM_ZOOM_INTRABAR_STOP",
    "PLATFORM_ZOOM_INTRABAR_TP",
]


@pytest.mark.parametrize(
    "strategy_name",
    [
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
    ],
)
def test_export_exit_time_comparison(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    """Export all trades with exit time comparison details to CSV.

    This test validates exit TIMES by categorizing all discrepancies.
    Uses parametrization to test multiple strategies with same logic.

    Args:
        strategy_name: Strategy to test (from parametrize)
        golden_strategy_config: Strategy config fixture
        tradingview_trades: TradingView trades fixture
        tradingview_ohlcv: TradingView OHLCV fixture
        tradingview_ohlcv_1min: TradingView 1-minute OHLCV fixture
        golden_metadata: Golden metadata fixture
        request: Pytest request object for marker access
    """
    # Mark this test with the strategy name for fixture selection
    request.node.add_marker(pytest.mark.strategy_name(strategy_name))

    date_range = golden_metadata.get("date_range")

    # Load platform trades
    platform_trades = load_platform_trades(
        strategy_name=strategy_name,
        run_config=golden_strategy_config["run_config"],
        ohlcv_data=tradingview_ohlcv,
        date_range=date_range,
        data_handler=shared_data_handler,
    )

    # Load and prepare trade data using utility function
    platform_df, tv_df = load_and_prepare_trade_data(
        strategy_name, platform_trades, golden_metadata
    )

    print(f"\nPlatform trades: {len(platform_df)}")
    print(f"TradingView trades: {len(tv_df)}")
    print(f"Total trades to compare: {min(len(platform_df), len(tv_df))}\n")

    # Get known edge cases for exit time mismatches
    strategy_edge_cases = KNOWN_EDGE_CASES.get(strategy_name, {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    print(f"Known exit time edge cases: {len(known_exit_time_edge_cases)}")
    if known_exit_time_edge_cases:
        print(
            "  Trade indices:",
            sorted([ec["trade_index"] + 1 for ec in known_exit_time_edge_cases]),
        )
    print()

    # Create analyzer using factory (auto-configured from metadata)
    analyzer = create_analyzer_for_strategy(golden_metadata)

    # Analyze discrepancies
    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    # Build lookup dictionaries using utility function
    category_lookup, explanation_lookup, mfe_data_lookup = build_category_lookup(
        categories
    )

    # Export comparison CSV using utility function
    output_path = Path("workspace/exit_time_comparison.csv")
    export_comparison_csv(
        platform_df,
        tv_df,
        output_path,
        "exit_time",
        category_lookup,
        explanation_lookup,
        mfe_data_lookup,
        known_edge_cases=known_exit_time_edge_cases,
        allowed_time_categories=EXIT_TIME_CATEGORIES,
    )

    # Verify comparison file hash matches golden reference
    verify_golden_comparison_hash(
        strategy_name,
        output_path,
        golden_filename="exit_time_comparison_golden.csv",
    )

    # Print summary statistics
    import pandas as pd

    comparison_df = pd.read_csv(output_path)
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

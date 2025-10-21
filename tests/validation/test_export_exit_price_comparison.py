#!/usr/bin/env python3
"""Export exit price comparison to CSV for trailing stop validation.

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
    verify_golden_comparison_hash,
)


@pytest.mark.parametrize(
    "strategy_name",
    [
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "ema_crossover/2atr_stop",
    ],
)
def test_export_exit_price_comparison(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    """Export all trades with exit price comparison details to CSV.

    This test validates exit PRICES by categorizing all discrepancies.
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

    # Get platform trades from session-scoped fixture based on strategy
    fixture_map = {
        "ema_crossover/20pip_stop": request.getfixturevalue(
            "platform_trades_20pip_stop"
        ),
        "ema_crossover/20pip_stop_40pip_tp": request.getfixturevalue(
            "platform_trades_20pip_stop_40pip_tp"
        ),
        "ema_crossover/20pip_trailing_stop": request.getfixturevalue(
            "platform_trades_20pip_trailing_stop"
        ),
        "ema_crossover/20pip_trailing_stop_15pip_tp": request.getfixturevalue(
            "platform_trades_20pip_trailing_stop_15pip_tp"
        ),
    }
    platform_trades = fixture_map[strategy_name]

    # Load and prepare trade data using utility function
    platform_df, tv_df = load_and_prepare_trade_data(
        strategy_name, platform_trades, golden_metadata
    )

    print(f"\nPlatform trades: {len(platform_df)}")
    print(f"TradingView trades: {len(tv_df)}")
    print(f"Total trades to compare: {min(len(platform_df), len(tv_df))}\n")

    # Get known edge cases (not typically used for price comparisons, but available)
    # strategy_edge_cases = KNOWN_EDGE_CASES.get(strategy_name, {})
    # known_exit_price_edge_cases = strategy_edge_cases.get("exit_price_mismatches", [])

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
    output_path = Path("workspace/exit_price_comparison.csv")
    export_comparison_csv(
        platform_df,
        tv_df,
        output_path,
        "exit_price",
        category_lookup,
        explanation_lookup,
        mfe_data_lookup,
    )

    # Verify comparison file hash matches golden reference
    verify_golden_comparison_hash(
        strategy_name,
        output_path,
        golden_filename="exit_price_comparison_golden.csv",
    )

    # Print summary statistics
    import pandas as pd

    comparison_df = pd.read_csv(output_path)
    total_trades = len(comparison_df)
    price_matches = comparison_df["exit_price_match"].sum()
    price_mismatches = total_trades - price_matches

    print(f"\n{'='*80}")
    print("EXIT PRICE VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total trades: {total_trades}")
    print(f"Exit prices match: {price_matches}")
    print(f"Exit prices mismatch: {price_mismatches}")

    if price_mismatches > 0:
        print("\nPrice Mismatch Categories:")
        category_counts = comparison_df[~comparison_df["exit_price_match"]][
            "failure_category"
        ].value_counts()
        for category, count in category_counts.items():
            print(f"  {category}: {count}")

    print(f"{'='*80}\n")

    # Assert all price mismatches are explained
    unexplained = comparison_df[comparison_df["failure_category"] == "UNEXPLAINED"]

    assert len(unexplained) == 0, (
        f"Found {len(unexplained)} UNEXPLAINED exit price mismatches!\n"
        f"All price discrepancies must be categorized and explained.\n"
        f"See {output_path} for details."
    )

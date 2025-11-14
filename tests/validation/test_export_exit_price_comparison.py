#!/usr/bin/env python3
"""Export exit price comparison to CSV for trailing stop validation.

This module has been refactored to use shared utility functions and
parametrization to eliminate code duplication.
"""

from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from tests.validation.analyzers import create_analyzer_for_strategy
from tests.validation.comparison_export import export_comparison_csv
from tests.validation.comparison_utils import build_category_lookup
from tests.validation.golden_utils import load_and_prepare_trade_data
from tests.validation.test_strategy_validation import (
    verify_golden_comparison_hash,
)

_EXIT_PRICE_CACHE: Dict[str, Dict[str, Any]] = {}


def _comparison_path(strategy_name: str, comparison_type: str) -> Path:
    slug = strategy_name.replace("/", "_")
    return Path("workspace") / "comparison_exports" / f"{slug}_{comparison_type}.csv"


def _run_exit_price_export(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    cached = _EXIT_PRICE_CACHE.get(strategy_name)
    if cached:
        return cached

    request.node.add_marker(pytest.mark.strategy_name(strategy_name))

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
        "ema_crossover/2atr_stop": request.getfixturevalue("platform_trades_2atr_stop"),
        "ema_crossover/bb_stop": request.getfixturevalue("platform_trades_bb_stop"),
    }
    platform_trades = fixture_map[strategy_name]

    platform_df, tv_df = load_and_prepare_trade_data(
        strategy_name, platform_trades, golden_metadata
    )

    print(f"\nPlatform trades: {len(platform_df)}")
    print(f"TradingView trades: {len(tv_df)}")
    print(f"Total trades to compare: {min(len(platform_df), len(tv_df))}\n")

    analyzer = create_analyzer_for_strategy(golden_metadata)
    categories = analyzer.analyze_discrepancies(
        platform_df=platform_df,
        tv_df=tv_df,
        ohlcv_data=tradingview_ohlcv,
        ohlcv_1min=tradingview_ohlcv_1min,
    )

    category_lookup, explanation_lookup, mfe_data_lookup = build_category_lookup(
        categories
    )

    output_path = _comparison_path(strategy_name, "exit_price")
    export_comparison_csv(
        platform_df,
        tv_df,
        output_path,
        "exit_price",
        category_lookup,
        explanation_lookup,
        mfe_data_lookup,
    )

    comparison_df = pd.read_csv(output_path)

    result = {"path": output_path, "comparison_df": comparison_df}
    _EXIT_PRICE_CACHE[strategy_name] = result
    return result


@pytest.mark.parametrize(
    "strategy_name",
    [
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "ema_crossover/2atr_stop",
        "ema_crossover/bb_stop",
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
    result = _run_exit_price_export(
        strategy_name,
        golden_strategy_config,
        tradingview_trades,
        tradingview_ohlcv,
        tradingview_ohlcv_1min,
        golden_metadata,
        shared_data_handler,
        request,
    )

    comparison_df = result["comparison_df"]
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
        f"See {result['path']} for details."
    )


@pytest.mark.parametrize(
    "strategy_name",
    [
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "ema_crossover/2atr_stop",
        "ema_crossover/bb_stop",
    ],
)
def test_exit_price_comparison_matches_golden(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    """Ensure exit price comparison CSV still matches the frozen golden file."""
    result = _run_exit_price_export(
        strategy_name,
        golden_strategy_config,
        tradingview_trades,
        tradingview_ohlcv,
        tradingview_ohlcv_1min,
        golden_metadata,
        shared_data_handler,
        request,
    )
    verify_golden_comparison_hash(
        strategy_name,
        result["path"],
        golden_filename="exit_price_comparison_golden.csv",
    )

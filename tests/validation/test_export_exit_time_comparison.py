#!/usr/bin/env python3
"""Export exit time comparison to CSV for trailing stop validation.

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
    KNOWN_EDGE_CASES,
    verify_golden_comparison_hash,
)

# Define allowed categories that explain exit TIME mismatches
EXIT_TIME_CATEGORIES = [
    "SAME_BAR_EXIT",
    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT",
    "TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED",
    "PLATFORM_ZOOM_INTRABAR_STOP",
    "PLATFORM_ZOOM_INTRABAR_TP",
    "BOLLINGER_BAND_SHIFT",
]

_EXIT_TIME_CACHE: Dict[str, Dict[str, Any]] = {}


def _comparison_path(strategy_name: str, comparison_type: str) -> Path:
    slug = strategy_name.replace("/", "_")
    return Path("workspace") / "comparison_exports" / f"{slug}_{comparison_type}.csv"


def _run_exit_time_export(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    cached = _EXIT_TIME_CACHE.get(strategy_name)
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

    strategy_edge_cases = KNOWN_EDGE_CASES.get(strategy_name, {})
    known_exit_time_edge_cases = strategy_edge_cases.get("exit_time_mismatches", [])

    print(f"Known exit time edge cases: {len(known_exit_time_edge_cases)}")
    if known_exit_time_edge_cases:
        print(
            "  Trade indices:",
            sorted([ec["trade_index"] + 1 for ec in known_exit_time_edge_cases]),
        )
    print()

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

    output_path = _comparison_path(strategy_name, "exit_time")
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

    comparison_df = pd.read_csv(output_path)

    result = {"path": output_path, "comparison_df": comparison_df}
    _EXIT_TIME_CACHE[strategy_name] = result
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
    result = _run_exit_time_export(
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
def test_exit_time_comparison_matches_golden(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    shared_data_handler,
    request,
):
    """Ensure exit time comparison CSV still matches the frozen golden file."""
    result = _run_exit_time_export(
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
        golden_filename="exit_time_comparison_golden.csv",
    )

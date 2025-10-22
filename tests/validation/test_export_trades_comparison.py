#!/usr/bin/env python3
"""Export unified trade comparisons for debugging purposes."""

from pathlib import Path

import pandas as pd
import pytest

from tests.validation.analyzers import create_analyzer_for_strategy
from tests.validation.comparison_export import export_comparison_csv
from tests.validation.comparison_utils import build_category_lookup
from tests.validation.golden_utils import load_and_prepare_trade_data
from tests.validation.test_export_exit_time_comparison import EXIT_TIME_CATEGORIES
from tests.validation.test_strategy_validation import KNOWN_EDGE_CASES


@pytest.mark.strategy_name("ema_crossover/20pip_trailing_stop")
def test_export_all_trades_comparison(
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    platform_trades_20pip_trailing_stop,
):
    """Export merged exit-time and exit-price comparisons for all trades."""
    strategy_name = "ema_crossover/20pip_trailing_stop"
    platform_df, tv_df = load_and_prepare_trade_data(
        strategy_name,
        platform_trades_20pip_trailing_stop,
        golden_metadata,
    )

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

    strategy_edge_cases = KNOWN_EDGE_CASES.get(strategy_name, {})
    known_exit_time_edge_cases = strategy_edge_cases.get(
        "exit_time_mismatches", []
    )

    workspace = Path("workspace")
    workspace.mkdir(parents=True, exist_ok=True)

    exit_time_path = workspace / "all_trades_exit_time_comparison.csv"
    exit_price_path = workspace / "all_trades_exit_price_comparison.csv"
    combined_path = workspace / "all_trades_comparison.csv"

    export_comparison_csv(
        platform_df,
        tv_df,
        exit_time_path,
        "exit_time",
        category_lookup,
        explanation_lookup,
        mfe_data_lookup,
        known_edge_cases=known_exit_time_edge_cases,
        allowed_time_categories=EXIT_TIME_CATEGORIES,
    )

    export_comparison_csv(
        platform_df,
        tv_df,
        exit_price_path,
        "exit_price",
        category_lookup,
        explanation_lookup,
        mfe_data_lookup,
    )

    time_df = pd.read_csv(exit_time_path)
    price_df = pd.read_csv(exit_price_path)[
        [
            "trade_num",
            "exit_price_match",
            "exit_price_diff_pips",
            "pnl_diff_pips",
            "failure_category",
            "failure_explanation",
        ]
    ].rename(
        columns={
            "failure_category": "price_failure_category",
            "failure_explanation": "price_failure_explanation",
        }
    )

    combined_df = time_df.merge(price_df, on="trade_num", how="left")
    combined_df.to_csv(combined_path, index=False)

    unexplained_time = combined_df[
        combined_df["time_mismatch_category"] == "UNEXPLAINED"
    ]
    assert len(unexplained_time) == 0, (
        "Found unexplained exit-time discrepancies in all trades export. "
        f"See {combined_path}"
    )

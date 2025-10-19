#!/usr/bin/env python3
"""CSV Export Utilities for Trade Comparison Tests

This module consolidates CSV export logic used across multiple validation tests
to eliminate duplication and ensure consistency.
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def calculate_pnl_pips(
    exit_price: float,
    entry_price: float,
    direction: str,
) -> float:
    """Calculate PnL in pips for a trade.

    Args:
        exit_price: Exit price
        entry_price: Entry price
        direction: Trade direction ("LONG" or "SHORT")

    Returns:
        PnL in pips
    """
    price_diff = exit_price - entry_price
    if direction.upper() == "SHORT":
        price_diff = -price_diff
    return price_diff * 10000


def build_exit_time_comparison_row(
    trade_num: int,
    platform_trade: pd.Series,
    tv_trade: pd.Series,
    category_lookup: Dict[int, str],
    explanation_lookup: Dict[int, str],
    mfe_data_lookup: Dict[int, Dict],
    known_edge_cases: List[dict],
    allowed_time_categories: List[str],
) -> dict:
    """Build a single row for exit time comparison CSV.

    Args:
        trade_num: 1-indexed trade number
        platform_trade: Platform trade Series
        tv_trade: TradingView trade Series
        category_lookup: Analyzer category assignments
        explanation_lookup: Analyzer explanations
        mfe_data_lookup: MFE data lookup
        known_edge_cases: List of known edge case dicts
        allowed_time_categories: Categories that explain time mismatches

    Returns:
        Dictionary with all fields for CSV row
    """
    from tests.validation.comparison_utils import lookup_known_edge_case

    # Extract basic data
    platform_exit_time = platform_trade["exit_time"]
    tv_exit_time = tv_trade["exit_time"]
    platform_exit_price = platform_trade["exit_price"]
    tv_exit_price = tv_trade["exit_price"]
    entry_price = platform_trade["entry_price"]
    p_direction = platform_trade.get(
        "direction", platform_trade.get("side", "")
    ).upper()

    # Calculate differences
    exit_price_diff_pips = abs(platform_exit_price - tv_exit_price) * 10000

    # Calculate PnL
    if "pnl_pips" in platform_trade:
        platform_pnl_pips = platform_trade["pnl_pips"]
    else:
        platform_pnl_pips = calculate_pnl_pips(
            platform_exit_price, entry_price, p_direction
        )

    if "pnl_pips" in tv_trade:
        tv_pnl_pips = tv_trade["pnl_pips"]
    else:
        tv_pnl_pips = calculate_pnl_pips(
            tv_exit_price, entry_price, tv_trade.get("side", "").upper()
        )

    pnl_diff_pips = platform_pnl_pips - tv_pnl_pips

    # Get MFE data
    mfe_data = mfe_data_lookup.get(trade_num, {})
    entry_bar_mfe = mfe_data.get("entry_bar_mfe_pips")
    subsequent_bars_mfe = mfe_data.get("overall_mfe_excl_entry_pips")

    # Calculate MFE difference
    if entry_bar_mfe is not None and subsequent_bars_mfe is not None:
        mfe_diff = entry_bar_mfe - subsequent_bars_mfe
    else:
        mfe_diff = None

    # Check if times match
    exit_time_match = platform_exit_time == tv_exit_time

    # Determine time mismatch category
    time_mismatch_category = ""
    time_mismatch_explanation = ""

    if not exit_time_match:
        trade_index = trade_num - 1  # Convert to 0-indexed

        # Check known edge cases first
        edge_case = lookup_known_edge_case(trade_index, known_edge_cases)
        if edge_case:
            time_mismatch_category = "KNOWN_EDGE_CASE"
            time_mismatch_explanation = edge_case.get("description", "")
        else:
            # Check analyzer categories
            analyzer_category = category_lookup.get(trade_num, "")
            if analyzer_category in allowed_time_categories:
                time_mismatch_category = analyzer_category
                time_mismatch_explanation = explanation_lookup.get(trade_num, "")
            else:
                time_mismatch_category = "UNEXPLAINED"
                time_mismatch_explanation = (
                    "Exit time discrepancy requires investigation."
                )

    return {
        "trade_num": trade_num,
        "direction": p_direction,
        "entry_time": str(platform_trade["entry_time"]),
        "entry_price": entry_price,
        "platform_exit_time": str(platform_exit_time),
        "platform_exit_price": platform_exit_price,
        "tv_exit_time": str(tv_exit_time),
        "tv_exit_price": tv_exit_price,
        "exit_time_match": exit_time_match,
        "exit_price_diff_pips": exit_price_diff_pips,
        "pnl_diff_pips": pnl_diff_pips,
        "entry_bar_mfe_pips": entry_bar_mfe,
        "subsequent_bars_mfe_pips": subsequent_bars_mfe,
        "mfe_diff_pips": mfe_diff,
        "time_mismatch_category": time_mismatch_category,
        "time_mismatch_explanation": time_mismatch_explanation,
    }


def build_exit_price_comparison_row(
    trade_num: int,
    platform_trade: pd.Series,
    tv_trade: pd.Series,
    category_lookup: Dict[int, str],
    explanation_lookup: Dict[int, str],
    mfe_data_lookup: Dict[int, Dict],
) -> dict:
    """Build a single row for exit price comparison CSV.

    Args:
        trade_num: 1-indexed trade number
        platform_trade: Platform trade Series
        tv_trade: TradingView trade Series
        category_lookup: Analyzer category assignments
        explanation_lookup: Analyzer explanations
        mfe_data_lookup: MFE data lookup

    Returns:
        Dictionary with all fields for CSV row
    """
    # Extract basic data
    entry_time = platform_trade["entry_time"]
    entry_price = platform_trade["entry_price"]
    platform_exit_time = platform_trade["exit_time"]
    platform_exit_price = platform_trade["exit_price"]
    tv_exit_time = tv_trade["exit_time"]
    tv_exit_price = tv_trade["exit_price"]

    p_direction = platform_trade.get(
        "direction", platform_trade.get("side", "")
    ).upper()

    # Get platform exit reason
    platform_exit_reason = platform_trade.get("exit_reason", "")

    # Calculate PnL
    platform_pnl_pips = calculate_pnl_pips(
        platform_exit_price, entry_price, p_direction
    )

    # Get TV exit reason
    tv_exit_reason = tv_trade.get("exit_reason", "")

    # Calculate TV PnL
    tv_pnl_pips = calculate_pnl_pips(
        tv_exit_price, entry_price, tv_trade.get("side", "").upper()
    )

    # Check if prices match
    exit_price_match = abs(platform_exit_price - tv_exit_price) < 0.00001
    exit_price_diff_pips = abs(platform_exit_price - tv_exit_price) * 10000
    pnl_diff_pips = platform_pnl_pips - tv_pnl_pips

    # Get MFE data
    mfe_data = mfe_data_lookup.get(trade_num, {})
    entry_bar_mfe = mfe_data.get("entry_bar_mfe_pips")
    subsequent_bars_mfe = mfe_data.get("overall_mfe_excl_entry_pips")

    # Calculate MFE difference
    if entry_bar_mfe is not None and subsequent_bars_mfe is not None:
        mfe_diff = entry_bar_mfe - subsequent_bars_mfe
    else:
        mfe_diff = None

    # Get category and explanation ONLY if prices don't match
    # For exit price comparison, we only care about PRICE discrepancies
    # (The analyzer may categorize trades with time mismatches but price matches,
    # which shouldn't be treated as failures in exit price comparison)
    if exit_price_match:
        failure_category = ""
        failure_explanation = ""
    else:
        # Use "failure_category" for backward compatibility with golden files
        failure_category = category_lookup.get(trade_num, "")
        failure_explanation = explanation_lookup.get(trade_num, "")

    return {
        "trade_num": trade_num,
        "direction": p_direction,
        "entry_time": str(entry_time),
        "entry_price": entry_price,
        "platform_exit_time": str(platform_exit_time),
        "platform_exit_price": platform_exit_price,
        "platform_exit_reason": platform_exit_reason,
        "platform_pnl_pips": platform_pnl_pips,
        "tv_exit_time": str(tv_exit_time),
        "tv_exit_price": tv_exit_price,
        "tv_exit_reason": tv_exit_reason,
        "tv_pnl_pips": tv_pnl_pips,
        "exit_price_match": exit_price_match,
        "exit_price_diff_pips": exit_price_diff_pips,
        "pnl_diff_pips": pnl_diff_pips,
        "entry_bar_mfe_pips": entry_bar_mfe,
        "subsequent_bars_mfe_pips": subsequent_bars_mfe,
        "mfe_diff_pips": mfe_diff,
        "failure_category": failure_category,
        "failure_explanation": failure_explanation,
    }


def export_comparison_csv(
    platform_df: pd.DataFrame,
    tv_df: pd.DataFrame,
    output_path: Path,
    comparison_type: str,
    category_lookup: Dict[int, str],
    explanation_lookup: Dict[int, str],
    mfe_data_lookup: Dict[int, Dict],
    known_edge_cases: Optional[List[dict]] = None,
    allowed_time_categories: Optional[List[str]] = None,
) -> Path:
    """Export trade comparison to CSV with configurable column sets.

    This consolidates the common pattern of building comparison rows
    and exporting to CSV across multiple test files.

    Args:
        platform_df: Platform trades DataFrame
        tv_df: TradingView trades DataFrame (aligned with platform_df)
        output_path: Output CSV file path
        comparison_type: Type of comparison ("exit_time", "exit_price", "all_trades")
        category_lookup: Category assignments from analyzer
        explanation_lookup: Explanations from analyzer
        mfe_data_lookup: MFE data from analyzer
        known_edge_cases: Optional list of known edge case dicts (for exit_time)
        allowed_time_categories: Optional list of categories that explain time
            mismatches (for exit_time)

    Returns:
        Path to the created CSV file

    Raises:
        ValueError: If comparison_type is invalid

    Example:
        >>> export_comparison_csv(
        ...     platform_df, tv_df,
        ...     Path("workspace/exit_time_comparison.csv"),
        ...     "exit_time",
        ...     cat_lookup, exp_lookup, mfe_lookup,
        ...     known_edge_cases=edge_cases,
        ...     allowed_time_categories=["SAME_BAR_EXIT", ...]
        ... )
    """
    if known_edge_cases is None:
        known_edge_cases = []

    comparison_rows = []

    for i in range(min(len(platform_df), len(tv_df))):
        p_row = platform_df.iloc[i]
        tv_row = tv_df.iloc[i]
        trade_num = i + 1

        if comparison_type == "exit_time":
            if allowed_time_categories is None:
                raise ValueError(
                    "allowed_time_categories required for exit_time comparison"
                )
            row = build_exit_time_comparison_row(
                trade_num,
                p_row,
                tv_row,
                category_lookup,
                explanation_lookup,
                mfe_data_lookup,
                known_edge_cases,
                allowed_time_categories,
            )
        elif comparison_type == "exit_price":
            row = build_exit_price_comparison_row(
                trade_num,
                p_row,
                tv_row,
                category_lookup,
                explanation_lookup,
                mfe_data_lookup,
            )
        else:
            raise ValueError(
                f"Invalid comparison_type: {comparison_type}. "
                f"Must be 'exit_time' or 'exit_price'"
            )

        comparison_rows.append(row)

    # Create DataFrame and save to CSV
    comparison_df = pd.DataFrame(comparison_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(output_path, index=False)

    print(f"✓ {comparison_type} comparison exported to: {output_path}")

    return output_path

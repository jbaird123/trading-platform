#!/usr/bin/env python3
"""Shared utility functions for comparison tests.

This module consolidates common patterns used across multiple validation
test files to eliminate code duplication and ensure consistency.
"""

from typing import Optional


def build_category_lookup(
    categories: dict[str, list[dict]],
) -> tuple[dict[int, str], dict[int, str], dict[int, dict]]:
    """Build lookup dictionaries from analyzer categories.

    Extracts category names, explanations, and MFE data indexed by trade number
    from the analyzer's categorized results.

    Args:
        categories: Dictionary of categorized trades from
            analyzer.analyze_discrepancies()
            Format: {category_name: [list of trade dicts with
            trade_num, explanation, etc.]}

    Returns:
        Tuple of (category_lookup, explanation_lookup, mfe_data_lookup):
        - category_lookup: {trade_num: category_name}
        - explanation_lookup: {trade_num: explanation_string}
        - mfe_data_lookup: {trade_num: {entry_bar_mfe_pips,
            overall_mfe_excl_entry_pips}}

    Example:
        >>> categories = analyzer.analyze_discrepancies(...)
        >>> cat_lookup, exp_lookup, mfe_lookup = build_category_lookup(categories)
        >>> cat_lookup[28]  # "PLATFORM_ZOOM_INTRABAR_STOP"
    """
    category_lookup: dict[int, str] = {}
    explanation_lookup: dict[int, str] = {}
    mfe_data_lookup: dict[int, dict] = {}

    for category_name, trades in categories.items():
        for trade in trades:
            trade_num = trade["trade_num"]
            category_lookup[trade_num] = category_name
            explanation_lookup[trade_num] = trade.get("explanation", "")

            # Extract MFE data if available
            mfe_data_lookup[trade_num] = {
                "entry_bar_mfe_pips": trade.get("entry_bar_mfe_pips", None),
                "overall_mfe_excl_entry_pips": trade.get(
                    "overall_mfe_excl_entry_pips", None
                ),
            }

    return category_lookup, explanation_lookup, mfe_data_lookup


def lookup_known_edge_case(
    trade_index: int,
    known_edge_cases: list[dict],
) -> Optional[dict]:
    """Look up a known edge case by trade index.

    Args:
        trade_index: 0-indexed trade position in sorted trade list
        known_edge_cases: List of edge case dictionaries with "trade_index" key

    Returns:
        Edge case dictionary if found, None otherwise.
        Edge case dict contains: trade_index, description, and optional metadata

    Example:
        >>> edge_case = lookup_known_edge_case(2, known_exit_time_edge_cases)
        >>> if edge_case:
        ...     print(edge_case["description"])
        "Platform more accurate - TV missed trailing stop hit"
    """
    for edge_case in known_edge_cases:
        if edge_case["trade_index"] == trade_index:
            return edge_case
    return None


def is_edge_case_or_explained(
    trade_index: int,
    trade_num: int,
    known_edge_cases: list[dict],
    category_lookup: dict[int, str],
    allowed_categories: list[str],
) -> tuple[bool, str, str]:
    """Check if a trade discrepancy is explained by known edge case or analyzer.

    This combines edge case lookup with analyzer category checking to determine
    if a discrepancy is acceptable/explained.

    Args:
        trade_index: 0-indexed trade position
        trade_num: 1-indexed trade number (trade_index + 1)
        known_edge_cases: List of documented edge cases
        category_lookup: Category assignments from analyzer
        allowed_categories: List of category names that explain this
            type of discrepancy

    Returns:
        Tuple of (is_explained, category, explanation):
        - is_explained: True if discrepancy is acceptable
        - category: Category name (e.g., "KNOWN_EDGE_CASE",
            "SAME_BAR_EXIT", "UNEXPLAINED")
        - explanation: Human-readable explanation string

    Example:
        >>> is_ok, cat, exp = is_edge_case_or_explained(
        ...     27, 28, known_cases, cat_lookup,
        ...     ["SAME_BAR_EXIT", "PLATFORM_ZOOM_INTRABAR_STOP"]
        ... )
        >>> cat  # "PLATFORM_ZOOM_INTRABAR_STOP"
    """
    # Check if it's a documented known edge case first
    edge_case = lookup_known_edge_case(trade_index, known_edge_cases)
    if edge_case:
        return True, "KNOWN_EDGE_CASE", edge_case.get("description", "")

    # Check if analyzer categorized it as an allowed category
    analyzer_category = category_lookup.get(trade_num, "")
    if analyzer_category in allowed_categories:
        # Note: explanation should come from explanation_lookup, not category_lookup
        # Caller should pass explanation_lookup separately or we return empty
        return True, analyzer_category, ""

    # Not explained
    return False, "UNEXPLAINED", "Discrepancy requires investigation."

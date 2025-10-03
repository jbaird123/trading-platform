"""Tests for RMM lookahead bias fix.

# Validates: RMM lookahead bias prevention (Bug #2 from RMM_BUGS_FIXED.md)

This test validates the critical fix to prevent lookahead bias in RMM regime projection.
Without the fix, at 10:05 AM on a 5min chart with 15min RMM, the system would use
the regime from the bar that opened at 10:00 AM (not closed until 10:15 AM).
With the fix, it correctly uses the regime from the bar that closed at 10:00 AM
(the 09:45-10:00 bar).
"""

from __future__ import annotations

import pandas as pd
from trading_platform.regime_market_manager.engine import RMMEngine


def test_project_to_index_prevents_lookahead_bias() -> None:
    """Verify that project_to_index shifts regime data by 1 bar to prevent lookahead.

    Scenario:
    - 15min RMM bars at 09:45, 10:00, 10:15
    - 5min trading bars at 09:45, 09:50, 09:55, 10:00, 10:05, 10:10, 10:15
    - At 10:05, we should use regime from the 09:45 bar (closed at 10:00)
    - We should NOT use regime from the 10:00 bar (not closed until 10:15)
    """
    engine = RMMEngine(config={})

    # Create 15min regime bars
    regime_index = pd.date_range("2024-01-01 09:45", periods=3, freq="15min")
    regime_data = pd.DataFrame(
        {
            "label": ["trend_up", "range", "trend_down"],
            "confidence": [0.9, 0.8, 0.9],
        },
        index=regime_index,
    )

    # Create 5min trading bars
    trading_index = pd.date_range("2024-01-01 09:45", periods=7, freq="5min")

    policy = {"min_confidence": 0.5}
    result = engine.project_to_index(regime_data, trading_index, policy)

    # Expected behavior with shift(1):
    # At 09:45: NaN (shifted, no prior bar) -> None
    # At 09:50: NaN (ffill can't fill from NaN) -> None
    # At 09:55: NaN (ffill can't fill from NaN) -> None
    # At 10:00: trend_up (uses shifted data from 09:45 position) ✅
    # At 10:05: trend_up (ffill from 10:00) ✅  <- CRITICAL: Not using 10:00 bar yet!
    # At 10:10: trend_up (ffill from 10:00) ✅  <- Still using 09:45 data!
    # At 10:15: range (uses shifted data from 10:00 position) ✅

    expected_labels = [
        None,         # 09:45 (shifted becomes NaN)
        None,         # 09:50 (ffill can't fill NaN)
        None,         # 09:55 (ffill can't fill NaN)
        "trend_up",   # 10:00 (uses 09:45 bar via shift)
        "trend_up",   # 10:05 (ffill from 10:00) <- CRITICAL TEST POINT
        "trend_up",   # 10:10 (ffill from 10:00)
        "range",      # 10:15 (uses 10:00 bar via shift)
    ]

    expected_sides = [
        ["long", "short"],  # None label gets both sides
        ["long", "short"],  # None label gets both sides
        ["long", "short"],  # None label gets both sides
        ["long"],       # trend_up
        ["long"],       # trend_up <- CRITICAL: Should be long, not range
        ["long"],       # trend_up
        ["long", "short"],  # range (after Bug #1 fix)
    ]

    assert len(result) == 7
    assert result["label"].tolist() == expected_labels
    assert result["allowed_sides"].tolist() == expected_sides

    # CRITICAL ASSERTION: At 10:05, must use regime from 09:45 bar
    idx_10_05 = trading_index[4]  # 10:05 AM
    assert result.loc[idx_10_05, "label"] == "trend_up", \
        "At 10:05 AM, must use regime from 09:45 bar (closed at 10:00), not 10:00 bar (closes at 10:15)"


def test_project_to_index_without_shift_would_cause_lookahead() -> None:
    """This test documents what WOULD happen without the shift(1) fix.

    This is a NEGATIVE test showing the buggy behavior for documentation purposes.
    We manually test the WRONG behavior to prove the fix is necessary.
    """
    # Create regime data WITHOUT the shift
    regime_index = pd.date_range("2024-01-01 09:45", periods=3, freq="15min")
    regime_data = pd.DataFrame(
        {
            "label": ["trend_up", "range", "trend_down"],
            "confidence": [0.9, 0.8, 0.9],
        },
        index=regime_index,
    )

    # Create 5min trading bars
    trading_index = pd.date_range("2024-01-01 09:45", periods=7, freq="5min")

    # Simulate buggy behavior (no shift)
    aligned = regime_data.reindex(
        regime_data.index.union(trading_index)
    ).sort_index().ffill()
    aligned = aligned.loc[trading_index]

    # Without shift, at 10:00-10:15, it would use the 10:00 bar (WRONG!)
    # 10:00 bar contains "range" label
    idx_10_00 = trading_index[3]  # 10:00 AM
    idx_10_05 = trading_index[4]  # 10:05 AM

    # This is the BUG - at 10:05, it uses "range" from 10:00 bar
    # But the 10:00 bar doesn't close until 10:15!
    assert aligned.loc[idx_10_00, "label"] == "range", \
        "Without shift, at 10:00 it incorrectly uses the 10:00 bar label (lookahead bias)"
    assert aligned.loc[idx_10_05, "label"] == "range", \
        "Without shift, at 10:05 it incorrectly uses the 10:00 bar label (lookahead bias)"


def test_allowed_sides_for_range_after_bug_fix() -> None:
    """Verify Bug #1 fix: 'range' labels now return ['long', 'short'] instead of []."""
    # Bug #1: Missing side mapping for non-directional labels
    # BEFORE: allowed_sides_for("range", 0.8, {}) -> []
    # AFTER:  allowed_sides_for("range", 0.8, {}) -> ["long", "short"]

    assert RMMEngine.allowed_sides_for("range", 0.8, {}) == ["long", "short"]
    assert RMMEngine.allowed_sides_for("unknown", 0.8, {}) == ["long", "short"]
    assert RMMEngine.allowed_sides_for("low_vol", 0.8, {}) == ["long", "short"]

    # Directional labels still work as before
    assert RMMEngine.allowed_sides_for("trend_up", 0.8, {}) == ["long"]
    assert RMMEngine.allowed_sides_for("trend_down", 0.8, {}) == ["short"]

    # Policy checks still work
    assert RMMEngine.allowed_sides_for("range", 0.3, {"min_confidence": 0.5}) == []
    assert RMMEngine.allowed_sides_for("range", 0.8, {"allow_labels": ["trend_up"]}) == []
    assert RMMEngine.allowed_sides_for("range", 0.8, {"block_labels": ["range"]}) == []


def test_end_to_end_rmm_no_lookahead_with_actual_backtest_timing() -> None:
    """Integration test simulating actual backtest timing with RMM filter.

    This test simulates the exact scenario from the bug report:
    - Trading on 5min bars
    - RMM filter on 15min bars
    - Verifying at 10:05 AM we use regime from completed bar only
    """
    config = {
        "timeframe": "15M",
        "features": [
            {
                "name": "adx",
                "type": "ADX",
                "params": {"length": 14},
                "source": "close",
            }
        ],
        "regimes": [
            {
                "label": "trending",
                "confidence": 0.9,
                "conditions": {
                    "all_of": [
                        {"condition": "is_above", "left": {"ref": "adx"}, "right": 25}
                    ]
                },
            },
            {
                "label": "range",
                "confidence": 0.8,
                "conditions": {
                    "all_of": [
                        {"condition": "is_below", "left": {"ref": "adx"}, "right": 25}
                    ]
                },
            },
        ],
    }

    engine = RMMEngine(config=config)

    # Create 15min OHLC data with ADX values
    # 09:45 bar: ADX = 30 (trending)
    # 10:00 bar: ADX = 20 (range)
    # 10:15 bar: ADX = 35 (trending)
    regime_index = pd.date_range("2024-01-01 09:45", periods=3, freq="15min")
    regime_ohlc = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [100.5, 101.5, 102.5],
            "low": [99.5, 100.5, 101.5],
            "close": [100.2, 101.2, 102.2],
            "volume": [1000, 1000, 1000],
        },
        index=regime_index,
    )

    # Classify regimes (this would compute ADX)
    # For simplicity, we'll manually create regime output
    regime_classified = pd.DataFrame(
        {
            "label": ["trending", "range", "trending"],
            "confidence": [0.9, 0.8, 0.9],
            "adx": [30.0, 20.0, 35.0],
        },
        index=regime_index,
    )

    # Create 5min trading index
    trading_index = pd.date_range("2024-01-01 09:45", periods=10, freq="5min")

    policy = {"min_confidence": 0.5}
    projected = engine.project_to_index(regime_classified, trading_index, policy)

    # At 10:05 (index 4), verify we're using regime from 09:45 bar (trending)
    # NOT the 10:00 bar (range) which hasn't closed yet
    idx_10_05 = trading_index[4]  # 10:05 AM

    assert projected.loc[idx_10_05, "label"] == "trending", \
        "CRITICAL: At 10:05 AM, must use 'trending' from 09:45 bar, not 'range' from 10:00 bar"
    assert projected.loc[idx_10_05, "adx"] == 30.0, \
        "CRITICAL: At 10:05 AM, must use ADX=30 from 09:45 bar, not ADX=20 from 10:00 bar"

    # At 10:15 and after, we can use the 10:00 bar (now closed)
    idx_10_15 = trading_index[6]  # 10:15 AM
    assert projected.loc[idx_10_15, "label"] == "range", \
        "At 10:15 AM, can now use 'range' from 10:00 bar (closed at 10:15)"
    assert projected.loc[idx_10_15, "adx"] == 20.0, \
        "At 10:15 AM, can now use ADX=20 from 10:00 bar"

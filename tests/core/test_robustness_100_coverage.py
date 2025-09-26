"""
Comprehensive test coverage for core/robustness.py to achieve 100% coverage.

This file targets the missing lines identified in the coverage report:
- Line 36: _block_bootstrap function b = 1 when b <= 0
- Line 43: _block_bootstrap function blk = values[:b] when block is empty
- Line 83: _pct function return float(vals[f]) when f == c
"""

from datetime import datetime
from unittest.mock import patch

from trading_platform.core.robustness import (
    monte_carlo_summary,
    parameter_search,
    walk_forward_summary,
)
from trading_platform.portfolio.trade import Trade


def test_monte_carlo_block_bootstrap_zero_block_len():
    """Test block_bootstrap mode with b <= 0 to hit line 36."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 12, 0),
            exit_time=datetime(2024, 1, 1, 13, 0),
            side="short",
            size=100.0,
            entry_price=1.1050,
            exit_price=1.1000,
            pnl=50.0,
            exit_reason="signal",
        ),
    ]

    # Use block_bootstrap mode with block_len=0 to trigger b <= 0 condition
    summary = monte_carlo_summary(
        trades,
        initial_cash=10000.0,
        trials=5,
        seed=42,
        mode="block_bootstrap_trades",
        block_len=0,  # This will trigger b <= 0, setting b = 1 on line 36
    )

    # Verify the summary is valid
    assert summary["mode"] == "block_bootstrap_trades"
    assert summary["trials"] == 5
    assert "final_equity" in summary
    assert "total_pnl" in summary
    assert "max_drawdown" in summary
    assert "win_rate" in summary


def test_monte_carlo_block_bootstrap_negative_block_len():
    """Test block_bootstrap mode with negative block_len to hit line 36."""
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=25.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 12, 0),
            exit_time=datetime(2024, 1, 1, 13, 0),
            side="short",
            size=100.0,
            entry_price=1.1050,
            exit_price=1.1025,
            pnl=25.0,
            exit_reason="signal",
        ),
    ]

    # Use block_bootstrap mode with negative block_len
    summary = monte_carlo_summary(
        trades,
        initial_cash=10000.0,
        trials=3,
        seed=123,
        mode="block_bootstrap_trades",
        block_len=-5,  # Negative value triggers b <= 0, setting b = 1 on line 36
    )

    # Verify the summary is valid
    assert summary["mode"] == "block_bootstrap_trades"
    assert summary["trials"] == 3


def test_monte_carlo_block_bootstrap_empty_block_line_43():
    """Test block_bootstrap to hit line 43 when block slice is empty."""
    # Create a single trade to force edge case in block sampling
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1100,
            pnl=100.0,
            exit_reason="signal",
        )
    ]

    # Mock random.randrange to return a value that creates an empty block slice
    # This should trigger line 43: blk = values[:b]
    with patch("trading_platform.core.robustness.random.randrange") as mock_rand:
        # Return index that will create empty slice
        mock_rand.return_value = (
            1  # For single element list, start=1 creates empty slice
        )

        summary = monte_carlo_summary(
            trades,
            initial_cash=10000.0,
            trials=2,
            seed=42,
            mode="block_bootstrap_trades",
            block_len=2,  # Block length > trade count to force edge case
        )

        # Verify function completed successfully despite edge case
        assert summary["mode"] == "block_bootstrap_trades"
        assert summary["trials"] == 2
        assert mock_rand.called


def test_monte_carlo_percentile_calculation_f_equals_c():
    """Test _pct function to hit line 83 when f == c."""
    # Create trades that will result in percentile calculation where f == c
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1001,
            pnl=1.0,  # Small PnL to create specific percentile scenarios
            exit_reason="signal",
        )
    ]

    # Use a single trial to create a scenario where sorted values list
    # has specific characteristics for percentile calculation
    summary = monte_carlo_summary(
        trades,
        initial_cash=10000.0,
        trials=1,  # Single trial creates edge case in percentile calculation
        seed=42,
        mode="bootstrap_trades",
    )

    # Verify percentiles are calculated correctly
    assert summary["mode"] == "bootstrap_trades"
    assert summary["trials"] == 1
    assert "final_equity" in summary
    assert "p05" in summary["final_equity"]
    assert "p95" in summary["final_equity"]

    # With single trial, p05 and p95 should be the same value,
    # triggering f == c condition in _pct function (line 83)
    assert summary["final_equity"]["p05"] == summary["final_equity"]["p95"]


def test_monte_carlo_single_value_percentiles():
    """Test percentile calculation with single value to ensure line 83 coverage."""
    # Single trade, single trial to ensure f == c in percentile calculation
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1010,
            pnl=10.0,
            exit_reason="signal",
        )
    ]

    summary = monte_carlo_summary(
        trades,
        initial_cash=1000.0,
        trials=1,  # Single trial ensures single value in percentile arrays
        seed=999,
        mode="bootstrap_trades",
    )

    # All percentiles should be identical with single trial
    final_eq = summary["final_equity"]
    total_pnl = summary["total_pnl"]
    max_dd = summary["max_drawdown"]
    win_rate = summary["win_rate"]

    # Verify p05 == p95 for all metrics (f == c case in _pct function)
    assert final_eq["p05"] == final_eq["p95"]
    assert total_pnl["p05"] == total_pnl["p95"]
    assert max_dd["p05"] == max_dd["p95"]
    assert win_rate["p05"] == win_rate["p95"]


def test_walk_forward_empty_oos_windows():
    """Test walk_forward with configuration that creates empty OOS windows."""
    # Create trades that will result in empty OOS windows for some splits
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1050,
            pnl=50.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 5, 10, 0),  # Large gap
            exit_time=datetime(2024, 1, 5, 11, 0),
            side="short",
            size=100.0,
            entry_price=1.1050,
            exit_price=1.1000,
            pnl=50.0,
            exit_reason="signal",
        ),
    ]

    # Use window/step that creates gaps where OOS windows are empty
    summary = walk_forward_summary(trades, window=1, step=3)

    # Verify summary handles empty OOS windows correctly
    assert "splits" in summary
    assert "oos_total_pnl" in summary
    assert isinstance(summary["oos_total_pnl"]["n_splits"], int)


def test_parameter_search_empty_results():
    """Test parameter search with no grid or random space to get empty results."""

    def dummy_evaluate(params):
        return 0.0

    # Call with no grid and no random space to get empty candidates
    result = parameter_search(
        grid=None, random_space=None, n_samples=None, evaluate=dummy_evaluate
    )

    # Should return default top result with empty params
    assert "top" in result
    assert "results" in result
    assert result["top"]["params"] == {}
    assert result["top"]["score"] == 0.0
    assert result["results"] == []


def test_parameter_search_single_result_sorting():
    """Test parameter search sorting with single result."""

    def evaluate_func(params):
        return float(params.get("x", 0))

    # Grid with single parameter combination
    result = parameter_search(
        grid={"x": [42]}, random_space=None, evaluate=evaluate_func
    )

    # Verify single result is handled correctly in sorting
    assert result["top"]["params"]["x"] == 42
    assert result["top"]["score"] == 42.0
    assert len(result["results"]) == 1


def test_walk_forward_single_trade_edge_cases():
    """Test walk forward with edge cases in trade handling."""
    # Single trade to test edge cases in split processing
    trade = Trade(
        symbol="EUR_USD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        side="long",
        size=100.0,
        entry_price=1.1000,
        exit_price=1.1020,
        pnl=20.0,
        exit_reason="signal",
    )

    # Test with large window that exceeds trade count
    summary = walk_forward_summary([trade], window=10, step=1)

    # Should handle single trade gracefully
    assert "splits" in summary
    assert "oos_total_pnl" in summary


def test_monte_carlo_edge_case_max_start_negative():
    """Test block bootstrap when max_start calculation results in edge cases."""
    # Create scenario where m < b to test max_start calculation
    trades = [
        Trade(
            symbol="EUR_USD",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            side="long",
            size=100.0,
            entry_price=1.1000,
            exit_price=1.1010,
            pnl=10.0,
            exit_reason="signal",
        )
    ]

    # Use large block_len relative to number of trades to test edge cases
    summary = monte_carlo_summary(
        trades,
        initial_cash=10000.0,
        trials=2,
        seed=42,
        mode="block_bootstrap_trades",
        block_len=10,  # Much larger than trade count
    )

    # Verify function handles edge case correctly
    assert summary["mode"] == "block_bootstrap_trades"
    assert summary["trials"] == 2

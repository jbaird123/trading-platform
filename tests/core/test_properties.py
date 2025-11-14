"""Property-based tests for trading platform metrics logical consistency.

This module implements Layer 2 of the accuracy validation strategy using
hypothesis for property-based testing to ensure logical relationships
between reported metrics are always sound.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import compute_overall_performance


def test_equity_and_pnl_are_consistent():
    """
    Property-based test to ensure equity calculations are consistent with PnL.

    Tests the fundamental relationship: final_equity = initial_equity + total_pnl
    """

    @given(
        initial_equity=st.floats(
            min_value=1000.0,
            max_value=1000000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        trade_pnls=st.lists(
            st.floats(
                min_value=-1000.0,
                max_value=1000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=0,
            max_size=50,
        ),
    )
    @settings(
        max_examples=200,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_equity_pnl_relationship(initial_equity: float, trade_pnls: list[float]):
        """Test that final equity always equals initial equity plus total PnL."""

        # Create mock trades with the specified PnL values
        base_time = datetime(2023, 1, 1, 10, 0, 0)
        trades = []

        for i, pnl in enumerate(trade_pnls):
            # Create a realistic trade that would produce this PnL
            if pnl >= 0:  # Winning trade
                entry_price = 100.0
                exit_price = entry_price + pnl  # Simple 1:1 size assumption
                side = "long"
            else:  # Losing trade
                entry_price = 100.0
                exit_price = entry_price + pnl  # pnl is negative
                side = "long"

            trade = Trade(
                symbol="TESTPAIR",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i + 1),
                entry_price=entry_price,
                exit_price=exit_price,
                side=side,
                size=1.0,  # Simple unit size
                pnl=pnl,
                exit_reason="signal",
            )
            trades.append(trade)

        # Calculate expected final equity
        expected_total_pnl = sum(trade_pnls)
        expected_final_equity = initial_equity + expected_total_pnl

        # Generate performance report
        performance = compute_overall_performance(trades, initial_equity)

        # Assert the fundamental relationship holds
        assert abs(performance["total_pnl"] - expected_total_pnl) < 0.01, (
            f"Total PnL mismatch: expected {expected_total_pnl}, "
            f"got {performance['total_pnl']}"
        )

        assert abs(performance["final_equity"] - expected_final_equity) < 0.01, (
            f"Final equity mismatch: expected {expected_final_equity}, "
            f"got {performance['final_equity']}"
        )

        assert abs(performance["initial_equity"] - initial_equity) < 0.01, (
            f"Initial equity mismatch: expected {initial_equity}, "
            f"got {performance['initial_equity']}"
        )

    # Run the property-based test
    test_equity_pnl_relationship()


def test_win_rate_is_always_valid():
    """
    Property-based test to ensure win rate is always between 0.0 and 1.0.

    Tests that win_rate = winning_trades / total_trades and is in valid range.
    """

    @given(
        trade_pnls=st.lists(
            st.floats(
                min_value=-1000.0,
                max_value=1000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=1,  # At least one trade to avoid division by zero
            max_size=50,
        )
    )
    def test_win_rate_bounds_and_calculation(trade_pnls: list[float]):
        """Test that win rate is always valid and correctly calculated."""

        # Create mock trades with the specified PnL values
        base_time = datetime(2023, 1, 1, 10, 0, 0)
        trades = []

        for i, pnl in enumerate(trade_pnls):
            # Create a trade with this PnL
            entry_price = 100.0
            exit_price = entry_price + pnl

            trade = Trade(
                symbol="TESTPAIR",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i + 1),
                entry_price=entry_price,
                exit_price=exit_price,
                side="long",
                size=1.0,
                pnl=pnl,
                exit_reason="signal",
            )
            trades.append(trade)

        # Calculate expected win rate manually
        winning_trades = sum(1 for pnl in trade_pnls if pnl > 0)
        total_trades = len(trade_pnls)
        expected_win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # Generate performance report
        initial_cash = 100000.0  # Arbitrary initial cash
        performance = compute_overall_performance(trades, initial_cash)

        # Assert win rate is always in valid range [0.0, 1.0]
        win_rate = performance["win_rate"]
        assert (
            0.0 <= win_rate <= 1.0
        ), f"Win rate {win_rate} is outside valid range [0.0, 1.0]"

        # Assert win rate calculation is correct
        assert abs(win_rate - expected_win_rate) < 0.01, (
            f"Win rate calculation error: expected {expected_win_rate}, "
            f"got {win_rate}"
        )

        # Additional logical constraints
        if all(pnl > 0 for pnl in trade_pnls):
            # All winning trades should give 100% win rate
            assert (
                abs(win_rate - 1.0) < 0.01
            ), f"All winners should give 100% win rate, got {win_rate}"

        if all(pnl <= 0 for pnl in trade_pnls):
            # No winning trades should give 0% win rate
            assert (
                abs(win_rate - 0.0) < 0.01
            ), f"No winners should give 0% win rate, got {win_rate}"

    # Run the property-based test
    test_win_rate_bounds_and_calculation()


def test_trade_count_consistency():
    """
    Property-based test to ensure n_trades is consistent with actual trade count.

    Additional property test to verify basic counting logic.
    """

    @given(n_trades=st.integers(min_value=0, max_value=100))
    def test_n_trades_matches_list_length(n_trades: int):
        """Test that n_trades always matches the actual number of trades."""

        # Create exactly n_trades mock trades
        base_time = datetime(2023, 1, 1, 10, 0, 0)
        trades = []

        for i in range(n_trades):
            trade = Trade(
                symbol="TESTPAIR",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i + 1),
                entry_price=100.0,
                exit_price=100.0,  # No PnL for simplicity
                side="long",
                size=1.0,
                pnl=0.0,
                exit_reason="signal",
            )
            trades.append(trade)

        # Generate performance report
        initial_cash = 100000.0
        performance = compute_overall_performance(trades, initial_cash)

        # Assert trade count is correct
        assert performance["n_trades"] == n_trades, (
            f"Trade count mismatch: expected {n_trades}, "
            f"got {performance['n_trades']}"
        )

        # Assert trade count matches list length
        assert performance["n_trades"] == len(trades), (
            f"Trade count doesn't match list length: "
            f"{performance['n_trades']} != {len(trades)}"
        )

    # Run the property-based test
    test_n_trades_matches_list_length()


if __name__ == "__main__":
    # Run all property-based tests when executed directly
    print("Running property-based tests...")

    test_equity_and_pnl_are_consistent()
    print("✅ Equity and PnL consistency test passed")

    test_win_rate_is_always_valid()
    print("✅ Win rate validity test passed")

    test_trade_count_consistency()
    print("✅ Trade count consistency test passed")

    print("\n🎉 All property-based tests passed! 🎉")
    print("✅ Layer 2 logical consistency validation complete!")

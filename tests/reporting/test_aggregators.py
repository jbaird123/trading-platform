"""Tests for aggregation logic in reporting."""

from datetime import datetime, timezone

import pytest
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.aggregators import (
    aggregate_simulated_hold_analysis,
)
from trading_platform.reporting.models.exit_analysis import (
    PostExitAnalysis,
    SimulatedHold,
    SimulatedHoldAnalysis,
)


@pytest.fixture
def trades_with_simulations():
    """
    Create a list of trades with simulated hold data.

    Trade 1 (long, opposite_signal exit):
      - 10-bar sim: hits stop-loss, loses more money
      - 20-bar sim: hits stop-loss later, loses even more

    Trade 2 (short, stop-loss exit):
      - 10-bar sim: held full period, gains money
      - 20-bar sim: hits take-profit, gains more

    Trade 3 (long, signal exit):
      - 10-bar sim: held full period, minor gain
      - 20-bar sim: hits take-profit, bigger gain
    """
    # Trade 1: Long position, exited via opposite_signal
    trade1_sim10 = SimulatedHold(
        hold_bars=10,
        simulated_pnl=-25.0,  # Original was -15, now -25
        pnl_change_vs_actual=-10.0,  # Lost an extra $10
        simulated_exit_reason="stop_loss",
        simulated_exit_bar_offset=7,
        mfe_during_hold=5.0,
        mfe_bar_offset=2,
        mae_during_hold=-15.0,
        mae_bar_offset=7,
    )

    trade1_sim20 = SimulatedHold(
        hold_bars=20,
        simulated_pnl=-35.0,  # Original was -15, now -35
        pnl_change_vs_actual=-20.0,  # Lost an extra $20
        simulated_exit_reason="stop_loss",
        simulated_exit_bar_offset=12,
        mfe_during_hold=8.0,
        mfe_bar_offset=3,
        mae_during_hold=-25.0,
        mae_bar_offset=12,
    )

    trade1 = Trade(
        symbol="USDJPY",
        entry_time=datetime(2025, 8, 12, 15, 0, tzinfo=timezone.utc),
        exit_time=datetime(2025, 8, 13, 3, 0, tzinfo=timezone.utc),
        entry_price=147.80,
        exit_price=148.08,
        side="long",
        size=10000.0,
        pnl=-15.0,
        exit_reason="opposite_signal",
        stop_loss=147.30,
        take_profit=148.30,
        pnl_movement=-13.0,
        cost_currency=2.0,
        bars_held=23,
        post_exit_analysis=None,  # Will be replaced
    )

    # Manually set post_exit_analysis as PostExitAnalysis
    trade1_with_analysis = trade1.__class__(
        **{
            **trade1.__dict__,
            "post_exit_analysis": PostExitAnalysis(
                simulated_holds=[trade1_sim10, trade1_sim20]
            ),
        }
    )

    # Trade 2: Short position, exited via stop-loss
    trade2_sim10 = SimulatedHold(
        hold_bars=10,
        simulated_pnl=10.0,  # Original was -20, now +10
        pnl_change_vs_actual=30.0,  # Gained $30 by holding
        simulated_exit_reason="held_full_period",
        simulated_exit_bar_offset=9,
        mfe_during_hold=35.0,
        mfe_bar_offset=7,
        mae_during_hold=-5.0,
        mae_bar_offset=2,
    )

    trade2_sim20 = SimulatedHold(
        hold_bars=20,
        simulated_pnl=45.0,  # Original was -20, now +45
        pnl_change_vs_actual=65.0,  # Gained $65 by holding
        simulated_exit_reason="take_profit",
        simulated_exit_bar_offset=15,
        mfe_during_hold=50.0,
        mfe_bar_offset=15,
        mae_during_hold=-5.0,
        mae_bar_offset=2,
    )

    trade2 = Trade(
        symbol="USDJPY",
        entry_time=datetime(2025, 8, 15, 3, 0, tzinfo=timezone.utc),
        exit_time=datetime(2025, 8, 15, 18, 0, tzinfo=timezone.utc),
        entry_price=147.28,
        exit_price=147.24,
        side="short",
        size=10000.0,
        pnl=-20.0,
        exit_reason="stop-loss",
        stop_loss=147.78,
        take_profit=146.78,
        pnl_movement=-18.0,
        cost_currency=2.0,
        bars_held=29,
        post_exit_analysis=None,
    )

    trade2_with_analysis = trade2.__class__(
        **{
            **trade2.__dict__,
            "post_exit_analysis": PostExitAnalysis(
                simulated_holds=[trade2_sim10, trade2_sim20]
            ),
        }
    )

    # Trade 3: Long position, exited via signal
    trade3_sim10 = SimulatedHold(
        hold_bars=10,
        simulated_pnl=22.0,  # Original was 20, now 22
        pnl_change_vs_actual=2.0,  # Slight gain
        simulated_exit_reason="held_full_period",
        simulated_exit_bar_offset=9,
        mfe_during_hold=15.0,
        mfe_bar_offset=5,
        mae_during_hold=-3.0,
        mae_bar_offset=1,
    )

    trade3_sim20 = SimulatedHold(
        hold_bars=20,
        simulated_pnl=50.0,  # Original was 20, now 50
        pnl_change_vs_actual=30.0,  # Good gain
        simulated_exit_reason="take_profit",
        simulated_exit_bar_offset=18,
        mfe_during_hold=35.0,
        mfe_bar_offset=18,
        mae_during_hold=-3.0,
        mae_bar_offset=1,
    )

    trade3 = Trade(
        symbol="USDJPY",
        entry_time=datetime(2025, 8, 19, 6, 0, tzinfo=timezone.utc),
        exit_time=datetime(2025, 8, 20, 10, 0, tzinfo=timezone.utc),
        entry_price=147.50,
        exit_price=147.70,
        side="long",
        size=10000.0,
        pnl=20.0,
        exit_reason="signal",
        stop_loss=147.00,
        take_profit=148.00,
        pnl_movement=22.0,
        cost_currency=2.0,
        bars_held=40,
        post_exit_analysis=None,
    )

    trade3_with_analysis = trade3.__class__(
        **{
            **trade3.__dict__,
            "post_exit_analysis": PostExitAnalysis(
                simulated_holds=[trade3_sim10, trade3_sim20]
            ),
        }
    )

    return [trade1_with_analysis, trade2_with_analysis, trade3_with_analysis]


class TestSimulatedHoldAggregation:
    """Test aggregate_simulated_hold_analysis function."""

    def test_aggregation_basic_structure(self, trades_with_simulations):
        """Test that aggregation returns correct structure."""
        result = aggregate_simulated_hold_analysis(trades_with_simulations)

        assert isinstance(result, SimulatedHoldAnalysis)
        assert "10" in result.by_hold_period
        assert "20" in result.by_hold_period

    def test_aggregation_10_bar_averages(self, trades_with_simulations):
        """Test 10-bar hold period aggregation."""
        result = aggregate_simulated_hold_analysis(trades_with_simulations)
        period_10 = result.by_hold_period["10"]

        # Average PnL change across 3 trades:
        # Trade 1: -10.0, Trade 2: +30.0, Trade 3: +2.0
        # Average = 22.0 / 3 = 7.33
        assert period_10.avg_pnl_change_realistic == pytest.approx(7.33, abs=0.01)

        # Average MFE (unrealistic):
        # Trade 1: 5.0, Trade 2: 35.0, Trade 3: 15.0
        # Average = 55.0 / 3 = 18.33
        assert period_10.avg_mfe_unrealistic == pytest.approx(18.33, abs=0.01)

        # Outcome distribution:
        # stop_loss: 1/3 = 33.3%, held_full_period: 2/3 = 66.7%
        assert period_10.outcome_distribution.stop_loss_hit == pytest.approx(
            33.33, abs=0.01
        )
        assert period_10.outcome_distribution.held_full_period == pytest.approx(
            66.67, abs=0.01
        )

    def test_aggregation_20_bar_averages(self, trades_with_simulations):
        """Test 20-bar hold period aggregation."""
        result = aggregate_simulated_hold_analysis(trades_with_simulations)
        period_20 = result.by_hold_period["20"]

        # Average PnL change across 3 trades:
        # Trade 1: -20.0, Trade 2: +65.0, Trade 3: +30.0
        # Average = 75.0 / 3 = 25.0
        assert period_20.avg_pnl_change_realistic == pytest.approx(25.0)

        # Outcome distribution:
        # stop_loss: 1/3, take_profit: 2/3
        assert period_20.outcome_distribution.stop_loss_hit == pytest.approx(
            33.33, abs=0.01
        )
        assert period_20.outcome_distribution.take_profit_hit == pytest.approx(
            66.67, abs=0.01
        )

    def test_aggregation_by_original_exit_reason(self, trades_with_simulations):
        """Test breakdown by original exit reason."""
        result = aggregate_simulated_hold_analysis(trades_with_simulations)
        period_10 = result.by_hold_period["10"]

        # opposite_signal (1 trade): -10.0
        # stop-loss (1 trade): +30.0
        # signal (1 trade): +2.0
        assert (
            period_10.avg_pnl_change_by_original_exit_reason["opposite_signal"] == -10.0
        )
        assert period_10.avg_pnl_change_by_original_exit_reason["stop-loss"] == 30.0
        assert period_10.avg_pnl_change_by_original_exit_reason["signal"] == 2.0

    def test_aggregation_empty_trades_list(self):
        """Test aggregation with no trades."""
        result = aggregate_simulated_hold_analysis([])

        assert isinstance(result, SimulatedHoldAnalysis)
        assert len(result.by_hold_period) == 0

    def test_aggregation_trades_without_simulations(self):
        """Test aggregation when trades have no simulated holds."""
        trade = Trade(
            symbol="USDJPY",
            entry_time=datetime(2025, 8, 12, 15, 0, tzinfo=timezone.utc),
            exit_time=datetime(2025, 8, 13, 3, 0, tzinfo=timezone.utc),
            entry_price=147.80,
            exit_price=148.08,
            side="long",
            size=10000.0,
            pnl=15.0,
            exit_reason="signal",
            post_exit_analysis=None,
        )

        result = aggregate_simulated_hold_analysis([trade])

        # Should handle gracefully with empty result
        assert isinstance(result, SimulatedHoldAnalysis)
        assert len(result.by_hold_period) == 0

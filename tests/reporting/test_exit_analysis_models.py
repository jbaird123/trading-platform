"""Tests for exit analysis Pydantic models."""

import pytest
from pydantic import ValidationError
from trading_platform.reporting.models.exit_analysis import (
    PostExitAnalysis,
    SimulatedHold,
)


class TestSimulatedHold:
    """Test SimulatedHold model validation and behavior."""

    def test_valid_simulated_hold(self):
        """Test that SimulatedHold validates correctly with valid data."""
        hold = SimulatedHold(
            hold_bars=10,
            simulated_pnl=45.5,
            pnl_change_vs_actual=30.2,
            simulated_exit_reason="stop_loss",
            simulated_exit_bar_offset=7,
            mfe_during_hold=50.0,
            mfe_bar_offset=3,
            mae_during_hold=-10.0,
            mae_bar_offset=5,
        )
        assert hold.hold_bars == 10
        assert hold.simulated_pnl == 45.5
        assert hold.simulated_exit_reason == "stop_loss"

    def test_simulated_hold_with_take_profit(self):
        """Test SimulatedHold with take_profit exit reason."""
        hold = SimulatedHold(
            hold_bars=20,
            simulated_pnl=100.0,
            pnl_change_vs_actual=75.0,
            simulated_exit_reason="take_profit",
            simulated_exit_bar_offset=15,
            mfe_during_hold=110.0,
            mfe_bar_offset=14,
            mae_during_hold=-5.0,
            mae_bar_offset=2,
        )
        assert hold.simulated_exit_reason == "take_profit"

    def test_simulated_hold_with_held_full_period(self):
        """Test SimulatedHold with held_full_period exit reason."""
        hold = SimulatedHold(
            hold_bars=50,
            simulated_pnl=25.0,
            pnl_change_vs_actual=10.0,
            simulated_exit_reason="held_full_period",
            simulated_exit_bar_offset=50,
            mfe_during_hold=40.0,
            mfe_bar_offset=25,
            mae_during_hold=-15.0,
            mae_bar_offset=10,
        )
        assert hold.simulated_exit_reason == "held_full_period"
        assert hold.simulated_exit_bar_offset == 50

    def test_invalid_exit_reason_raises_validation_error(self):
        """Test that invalid exit_reason raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SimulatedHold(
                hold_bars=10,
                simulated_pnl=45.5,
                pnl_change_vs_actual=30.2,
                simulated_exit_reason="invalid_reason",
                simulated_exit_bar_offset=7,
                mfe_during_hold=50.0,
                mfe_bar_offset=3,
                mae_during_hold=-10.0,
                mae_bar_offset=5,
            )
        assert "simulated_exit_reason" in str(exc_info.value)

    def test_negative_hold_bars_allowed(self):
        """Test that negative hold_bars is allowed by the model.

        Note: Business logic validation should happen elsewhere.
        """
        hold = SimulatedHold(
            hold_bars=-5,
            simulated_pnl=0.0,
            pnl_change_vs_actual=0.0,
            simulated_exit_reason="stop_loss",
            simulated_exit_bar_offset=0,
            mfe_during_hold=0.0,
            mfe_bar_offset=0,
            mae_during_hold=0.0,
            mae_bar_offset=0,
        )
        # Model allows it; business logic should reject if needed
        assert hold.hold_bars == -5


class TestPostExitAnalysis:
    """Test PostExitAnalysis model validation and behavior."""

    def test_empty_post_exit_analysis(self):
        """Test that PostExitAnalysis can be created with empty list."""
        analysis = PostExitAnalysis()
        assert analysis.simulated_holds == []

    def test_post_exit_analysis_with_single_hold(self):
        """Test PostExitAnalysis with one SimulatedHold."""
        hold = SimulatedHold(
            hold_bars=10,
            simulated_pnl=45.5,
            pnl_change_vs_actual=30.2,
            simulated_exit_reason="stop_loss",
            simulated_exit_bar_offset=7,
            mfe_during_hold=50.0,
            mfe_bar_offset=3,
            mae_during_hold=-10.0,
            mae_bar_offset=5,
        )
        analysis = PostExitAnalysis(simulated_holds=[hold])
        assert len(analysis.simulated_holds) == 1
        assert analysis.simulated_holds[0].hold_bars == 10

    def test_post_exit_analysis_with_multiple_holds(self):
        """Test PostExitAnalysis with multiple SimulatedHold objects."""
        holds = [
            SimulatedHold(
                hold_bars=10,
                simulated_pnl=45.5,
                pnl_change_vs_actual=30.2,
                simulated_exit_reason="stop_loss",
                simulated_exit_bar_offset=7,
                mfe_during_hold=50.0,
                mfe_bar_offset=3,
                mae_during_hold=-10.0,
                mae_bar_offset=5,
            ),
            SimulatedHold(
                hold_bars=20,
                simulated_pnl=100.0,
                pnl_change_vs_actual=75.0,
                simulated_exit_reason="take_profit",
                simulated_exit_bar_offset=15,
                mfe_during_hold=110.0,
                mfe_bar_offset=14,
                mae_during_hold=-5.0,
                mae_bar_offset=2,
            ),
            SimulatedHold(
                hold_bars=50,
                simulated_pnl=25.0,
                pnl_change_vs_actual=10.0,
                simulated_exit_reason="held_full_period",
                simulated_exit_bar_offset=50,
                mfe_during_hold=40.0,
                mfe_bar_offset=25,
                mae_during_hold=-15.0,
                mae_bar_offset=10,
            ),
        ]
        analysis = PostExitAnalysis(simulated_holds=holds)
        assert len(analysis.simulated_holds) == 3
        assert analysis.simulated_holds[0].hold_bars == 10
        assert analysis.simulated_holds[1].hold_bars == 20
        assert analysis.simulated_holds[2].hold_bars == 50

    def test_post_exit_analysis_serialization(self):
        """Test that PostExitAnalysis can be serialized to dict."""
        hold = SimulatedHold(
            hold_bars=10,
            simulated_pnl=45.5,
            pnl_change_vs_actual=30.2,
            simulated_exit_reason="stop_loss",
            simulated_exit_bar_offset=7,
            mfe_during_hold=50.0,
            mfe_bar_offset=3,
            mae_during_hold=-10.0,
            mae_bar_offset=5,
        )
        analysis = PostExitAnalysis(simulated_holds=[hold])
        data = analysis.model_dump()
        assert "simulated_holds" in data
        assert len(data["simulated_holds"]) == 1
        assert data["simulated_holds"][0]["hold_bars"] == 10

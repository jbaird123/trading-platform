"""Additional tests to achieve 100% coverage for brief.py."""

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import (
    _extract_rem_policy,
    _to_jsonable,
    generate_brief,
)
from trading_platform.reporting.models.exit_analysis import (
    PostExitAnalysis,
    SimulatedHold,
)


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_extract_rem_policy_with_price_offsets() -> None:
    """Test _extract_rem_policy with stop_loss and take_profit price_offset.

    Validates: Lines 73-89, branches 70→73, 84-85, 86-87
    """
    config_snapshot = {
        "rem_config": {
            "stop_loss": {
                "enabled": True,
                "price_offset": 0.0050,  # 50 pips
            },
            "take_profit": {
                "enabled": True,
                "price_offset": 0.0100,  # 100 pips
            },
            "trailing_stop": {"enabled": False},
            "time_exit": {"max_bars": 10},
        }
    }

    result = _extract_rem_policy(config_snapshot)

    # Should extract policy structure
    assert "stop_loss" in result
    assert "take_profit" in result
    assert "trailing_stop" in result
    assert "time_exit" in result

    # Should have human-readable pips
    assert result["stop_loss_pips"] == "50 pips"
    assert result["take_profit_pips"] == "100 pips"


def test_extract_rem_policy_without_price_offsets() -> None:
    """Test _extract_rem_policy without price_offset fields."""
    config_snapshot = {
        "rem_config": {
            "stop_loss": {"enabled": False},  # No price_offset
            "take_profit": {"enabled": False},  # No price_offset
        }
    }

    result = _extract_rem_policy(config_snapshot)

    # Should extract basic structure but no pips
    assert "stop_loss" in result
    assert "take_profit" in result
    assert "stop_loss_pips" not in result
    assert "take_profit_pips" not in result


def test_to_jsonable_nan() -> None:
    """Test _to_jsonable converts NaN to None.

    Validates: Lines 244-245
    """
    result = _to_jsonable(float("nan"))
    assert result is None


def test_to_jsonable_inf() -> None:
    """Test _to_jsonable converts Inf to None.

    Validates: Lines 246-247
    """
    result = _to_jsonable(float("inf"))
    assert result is None

    result = _to_jsonable(float("-inf"))
    assert result is None


def test_serialize_trade_with_post_exit_dict() -> None:
    """Test trade serialization with post_exit_analysis as dict.

    Validates: Lines 312-313, branch 312→313
    """
    from dataclasses import replace

    # Create a trade with post_exit_analysis
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    trade = Trade(
        symbol="EURUSD",
        entry_time=entry_time,
        exit_time=entry_time + timedelta(hours=2),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=10000.0,
        pnl=50.0,
    )

    # Add post_exit_analysis using replace
    trade = replace(
        trade,
        post_exit_analysis=PostExitAnalysis(
            simulated_holds=[
                SimulatedHold(
                    hold_bars=5,
                    simulated_pnl=75.123456,
                    pnl_change_vs_actual=0.0,
                    simulated_exit_reason="held_full_period",
                    simulated_exit_bar_offset=5,
                    mfe_during_hold=75.123456,
                    mfe_bar_offset=0,
                    mae_during_hold=-25.987654,
                    mae_bar_offset=0,
                ),
                SimulatedHold(
                    hold_bars=10,
                    simulated_pnl=100.567890,
                    pnl_change_vs_actual=0.0,
                    simulated_exit_reason="held_full_period",
                    simulated_exit_bar_offset=10,
                    mfe_during_hold=100.567890,
                    mfe_bar_offset=0,
                    mae_during_hold=-15.234567,
                    mae_bar_offset=0,
                ),
            ]
        ),
    )

    # Generate brief with this trade
    brief = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=10000,
        field_definitions={},
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )

    # Verify trade was serialized with rounded post_exit_analysis
    assert "trades" in brief
    assert len(brief["trades"]) == 1
    serialized_trade = brief["trades"][0]
    assert "post_exit_analysis" in serialized_trade

    # Check new PostExitAnalysis format was serialized correctly
    post_exit = serialized_trade["post_exit_analysis"]
    assert "simulated_holds" in post_exit
    assert len(post_exit["simulated_holds"]) == 2

    # Verify the first simulated hold (5 bars)
    hold_5 = post_exit["simulated_holds"][0]
    assert hold_5["hold_bars"] == 5
    assert hold_5["mfe_during_hold"] == 75.123456
    assert hold_5["mae_during_hold"] == -25.987654

    # Verify the second simulated hold (10 bars)
    hold_10 = post_exit["simulated_holds"][1]
    assert hold_10["hold_bars"] == 10
    assert hold_10["mfe_during_hold"] == 100.567890
    assert hold_10["mae_during_hold"] == -15.234567


def test_generate_brief_with_rem_policy() -> None:
    """Test generate_brief includes rem_policy when present in config.

    Validates: Lines 793-795, branch 794→795
    """
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    trade = Trade(
        symbol="EURUSD",
        entry_time=entry_time,
        exit_time=entry_time + timedelta(hours=1),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=10000.0,
        pnl=50.0,
    )

    config_snapshot = {
        "rem_config": {
            "stop_loss": {"enabled": True, "price_offset": 0.0050},
            "take_profit": {"enabled": True, "price_offset": 0.0100},
        }
    }

    brief = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=10000,
        field_definitions={},
        config_snapshot=config_snapshot,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )

    # Should include rem_policy
    assert "rem_policy" in brief
    assert "stop_loss" in brief["rem_policy"]
    assert "stop_loss_pips" in brief["rem_policy"]
    assert brief["rem_policy"]["stop_loss_pips"] == "50 pips"


def test_generate_brief_without_rem_policy() -> None:
    """Test generate_brief when no rem_config in config_snapshot.

    Validates: Branch 794→next (false branch, rem_policy not updated)
    Line 777 always adds rem_policy to base, so it's always present.
    This test verifies the false branch where it's not updated with data.
    """
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    trade = Trade(
        symbol="EURUSD",
        entry_time=entry_time,
        exit_time=entry_time + timedelta(hours=1),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=10000.0,
        pnl=50.0,
    )

    # No config_snapshot - tests branch 794 false (rem_policy not updated)
    brief = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=10000,
        field_definitions={},
        config_snapshot=None,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )

    # rem_policy is always present (line 777), but should be empty
    assert "rem_policy" in brief
    assert brief["rem_policy"] == {}

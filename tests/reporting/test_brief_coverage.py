"""Additional tests to achieve 100% coverage for brief.py."""

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import (
    _extract_rem_policy,
    _round_dict_features,
    _round_feature,
    _to_jsonable,
    generate_brief,
)


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


def test_round_feature_adx_atr() -> None:
    """Test _round_feature for ADX and ATR indicators.

    Validates: Lines 191-194
    """
    assert _round_feature("adx", 23.456789) == 23.46
    assert _round_feature("atr", 0.0123456) == 0.012346
    assert _round_feature("ADX_14", 50.999) == 51.0


def test_round_feature_rsi_stoch_cci() -> None:
    """Test _round_feature for RSI, Stochastic, CCI indicators (2 decimals).

    Validates: Lines 197-200
    """
    assert _round_feature("rsi", 65.8765) == 65.88
    assert _round_feature("stoch_k", 32.1234) == 32.12
    assert _round_feature("cci", -45.678) == -45.68


def test_round_feature_volume() -> None:
    """Test _round_feature for volume (whole numbers).

    Validates: Lines 203-204
    """
    assert _round_feature("volume", 12345.6789) == 12346.0
    assert _round_feature("vol", 999.5) == 1000.0


def test_round_feature_ema_sma_prices() -> None:
    """Test _round_feature for EMA, SMA, and prices (4 decimals).

    Validates: Lines 207-213
    """
    assert _round_feature("ema_fast", 1.23456789) == 1.2346
    assert _round_feature("sma_20", 1.09876) == 1.0988
    assert _round_feature("close", 1.12345) == 1.1235
    assert _round_feature("open", 1.12345) == 1.1235
    assert _round_feature("high", 1.12345) == 1.1235
    assert _round_feature("low", 1.12345) == 1.1235


def test_round_feature_macd_momentum_roc() -> None:
    """Test _round_feature for MACD, momentum, ROC (4 decimals).

    Validates: Lines 216-219
    """
    assert _round_feature("macd", 0.012345678) == 0.0123
    assert _round_feature("momentum", -0.0056789) == -0.0057
    assert _round_feature("roc", 0.023456) == 0.0235


def test_round_feature_default() -> None:
    """Test _round_feature with unknown feature name (default 4 decimals).

    Validates: Lines 222-224
    """
    assert _round_feature("custom_indicator", 3.456789012) == 3.4568
    assert _round_feature("unknown", 1.99999) == 2.0


def test_round_feature_none() -> None:
    """Test _round_feature with None value.

    Validates: Lines 180-181
    """
    assert _round_feature("any_name", None) is None


def test_round_feature_nan() -> None:
    """Test _round_feature with NaN value.

    Validates: Lines 183-186
    """
    assert _round_feature("rsi", float("nan")) is None


def test_round_feature_inf() -> None:
    """Test _round_feature with Inf value.

    Validates: Lines 183-186
    """
    assert _round_feature("ema", float("inf")) is None
    assert _round_feature("ema", float("-inf")) is None


def test_round_feature_invalid_value() -> None:
    """Test _round_feature with invalid value type.

    Validates: Lines 226-227
    """
    assert _round_feature("rsi", "not_a_number") is None
    assert _round_feature("ema", {"invalid": "type"}) is None


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
        symbol="EUR_USD",
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
        post_exit_analysis={  # type: ignore[arg-type]
            "5": {"mfe": 75.123456, "mae": -25.987654},
            "10": {"mfe": 100.567890, "mae": -15.234567},
        },
    )

    # Generate brief with this trade
    brief = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=10000,
        field_definitions={},
    )

    # Verify trade was serialized with rounded post_exit_analysis
    assert "trades" in brief
    assert len(brief["trades"]) == 1
    serialized_trade = brief["trades"][0]
    assert "post_exit_analysis" in serialized_trade

    # Check rounding was applied
    post_exit = serialized_trade["post_exit_analysis"]
    assert "5" in post_exit
    assert post_exit["5"]["mfe"] == 75.12  # Rounded to 2 decimals
    assert post_exit["5"]["mae"] == -25.99


def test_generate_brief_with_rem_policy() -> None:
    """Test generate_brief includes rem_policy when present in config.

    Validates: Lines 793-795, branch 794→795
    """
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    trade = Trade(
        symbol="EUR_USD",
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
    )

    # Should include rem_policy
    assert "rem_policy" in brief
    assert "stop_loss" in brief["rem_policy"]
    assert "stop_loss_pips" in brief["rem_policy"]
    assert brief["rem_policy"]["stop_loss_pips"] == "50 pips"


def test_round_dict_features() -> None:
    """Test _round_dict_features rounds numeric values in dict.

    Validates: Line 232 - dict comprehension return
    """
    test_dict = {
        "rsi": 65.8765,
        "ema_fast": 1.23456789,
        "volume": 12345.6789,
        "text_field": "unchanged",
        "none_field": None,
    }

    result = _round_dict_features(test_dict)

    # Numeric values should be rounded
    assert result["rsi"] == 65.88
    assert result["ema_fast"] == 1.2346
    assert result["volume"] == 12346.0

    # Non-numeric values should be unchanged
    assert result["text_field"] == "unchanged"
    assert result["none_field"] is None


def test_generate_brief_without_rem_policy() -> None:
    """Test generate_brief when no rem_config in config_snapshot.

    Validates: Branch 794→next (false branch, rem_policy not updated)
    Line 777 always adds rem_policy to base, so it's always present.
    This test verifies the false branch where it's not updated with data.
    """
    entry_time = datetime(2024, 1, 1, 10, 0, 0)
    trade = Trade(
        symbol="EUR_USD",
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
    )

    # rem_policy is always present (line 777), but should be empty
    assert "rem_policy" in brief
    assert brief["rem_policy"] == {}

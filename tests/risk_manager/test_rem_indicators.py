"""Tests for REM Indicators Registry.

Tests the registry of indicators permitted for REM stop/TP calculations
and their associated calculator functions.
"""

import pandas as pd
import pytest
from trading_platform.risk_manager.rem_indicators import (
    REM_INDICATORS_REGISTRY,
    _calculate_atr_stop,
    _calculate_bollinger_stop,
)


class TestATRStopCalculator:
    """Tests for ATR-based stop calculator."""

    def test_atr_stop_calculator_long(self):
        """Test ATR stop calculation for long positions."""
        entry_price = 1.1000
        side = "long"
        current_bar = pd.Series({"close": 1.1000, "atr_14": 0.0020, "atr": 0.0020})
        params = {"multiplier": 2.0, "length": 14}

        result = _calculate_atr_stop(entry_price, side, current_bar, params)

        # Stop should be: close - (ATR * multiplier)
        # 1.1000 - (0.0020 * 2.0) = 1.0960
        assert result == pytest.approx(1.0960, abs=1e-6)

    def test_atr_stop_calculator_short(self):
        """Test ATR stop calculation for short positions."""
        entry_price = 1.1000
        side = "short"
        current_bar = pd.Series({"close": 1.1000, "atr_14": 0.0020})
        params = {"multiplier": 2.0, "length": 14}

        result = _calculate_atr_stop(entry_price, side, current_bar, params)

        # Stop should be: close + (ATR * multiplier)
        # 1.1000 + (0.0020 * 2.0) = 1.1040
        assert result == pytest.approx(1.1040, abs=1e-6)

    def test_atr_stop_uses_default_length(self):
        """Test ATR calculator uses default length when not specified."""
        entry_price = 1.2000
        side = "long"
        current_bar = pd.Series({"close": 1.2000, "atr": 0.0015})  # Generic ATR column
        params = {"multiplier": 1.5}  # No length specified

        result = _calculate_atr_stop(entry_price, side, current_bar, params)

        # Should use generic "atr" column.
        # Stop: close - (ATR * multiplier)
        # 1.2000 - (0.0015 * 1.5) = 1.19775
        assert result == pytest.approx(1.19775, abs=1e-6)

    def test_atr_stop_prefers_specific_length_column(self):
        """Test ATR calculator prefers atr_{length} column over generic atr."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "close": 1.3000,
                "atr_14": 0.0020,
                "atr": 0.0010,  # Should be ignored in favor of atr_14
            }
        )
        params = {"multiplier": 2.0, "length": 14}

        result = _calculate_atr_stop(entry_price, side, current_bar, params)

        # Should use atr_14, not generic atr.
        # Stop: close - (ATR * multiplier)
        # 1.3000 - (0.0020 * 2.0) = 1.2960
        assert result == pytest.approx(1.2960, abs=1e-6)

    def test_atr_stop_missing_indicator_raises_error(self):
        """Test that missing ATR column raises KeyError."""
        entry_price = 1.1000
        side = "long"
        current_bar = pd.Series({"close": 1.1050})  # No ATR column
        params = {"multiplier": 2.0, "length": 14}

        with pytest.raises(KeyError, match="ATR indicator not found"):
            _calculate_atr_stop(entry_price, side, current_bar, params)

    def test_atr_stop_missing_multiplier_raises_error(self):
        """Test that missing multiplier parameter raises KeyError."""
        entry_price = 1.1000
        side = "long"
        current_bar = pd.Series({"close": 1.1000, "atr_14": 0.0020})
        params = {"length": 14}  # Missing multiplier!

        with pytest.raises(KeyError, match="multiplier"):
            _calculate_atr_stop(entry_price, side, current_bar, params)

    def test_atr_stop_invalid_side_raises_error(self):
        """Test that invalid side parameter raises ValueError."""
        entry_price = 1.1000
        side = "invalid"
        current_bar = pd.Series({"close": 1.1000, "atr_14": 0.0020})
        params = {"multiplier": 2.0, "length": 14}

        with pytest.raises(ValueError, match="Invalid side"):
            _calculate_atr_stop(entry_price, side, current_bar, params)


class TestBollingerStopCalculator:
    """Tests for Bollinger-based stop calculator."""

    def test_bollinger_stop_long_uses_auto_band(self) -> None:
        entry_price = 1.2050
        side = "long"
        current_bar = pd.Series({"bb_lower": 1.1980, "bb_upper": 1.2100})
        params: dict[str, object] = {}

        result = _calculate_bollinger_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.1980, abs=1e-6)

    def test_bollinger_stop_short_uses_upper_band(self) -> None:
        entry_price = 1.2050
        side = "short"
        current_bar = pd.Series({"bb_lower": 1.1980, "bb_upper": 1.2100})
        params = {"band": "auto"}

        result = _calculate_bollinger_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.2100, abs=1e-6)

    def test_bollinger_stop_applies_offset(self) -> None:
        entry_price = 1.2050
        side = "long"
        current_bar = pd.Series({"bb_lower": 1.1980})
        params = {"band": "lower", "offset": 0.0005}

        result = _calculate_bollinger_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.1975, abs=1e-6)

    def test_bollinger_stop_supports_alternate_prefix(self) -> None:
        entry_price = 1.2050
        side = "long"
        current_bar = pd.Series({"bollinger_lower": 1.1970})
        params = {"band": "lower", "column_prefix": "bollinger"}

        result = _calculate_bollinger_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.1970, abs=1e-6)

    def test_bollinger_stop_missing_column_raises(self) -> None:
        entry_price = 1.2050
        side = "long"
        current_bar = pd.Series({"close": 1.2050})
        params = {"band": "lower"}

        with pytest.raises(KeyError, match="Bollinger indicator not found"):
            _calculate_bollinger_stop(entry_price, side, current_bar, params)

    def test_bollinger_stop_invalid_band_raises(self) -> None:
        entry_price = 1.2050
        side = "long"
        current_bar = pd.Series({"bb_lower": 1.1980})
        params = {"band": "invalid"}

        with pytest.raises(ValueError, match="Invalid Bollinger band"):
            _calculate_bollinger_stop(entry_price, side, current_bar, params)

    def test_bollinger_stop_invalid_side_raises(self) -> None:
        entry_price = 1.2050
        side = "flat"
        current_bar = pd.Series({"bb_lower": 1.1980})
        params = {"band": "lower"}

        with pytest.raises(ValueError, match="Invalid side"):
            _calculate_bollinger_stop(entry_price, side, current_bar, params)


class TestREMIndicatorsRegistry:
    """Tests for REM indicators registry."""

    def test_registry_contains_atr(self):
        """Verify ATR is registered."""
        assert "atr" in REM_INDICATORS_REGISTRY
        assert REM_INDICATORS_REGISTRY["atr"].name == "atr"

    def test_atr_spec_has_required_params(self):
        """Verify ATR spec defines required parameters."""
        atr_spec = REM_INDICATORS_REGISTRY["atr"]
        assert "multiplier" in atr_spec.required_params
        assert atr_spec.required_params["multiplier"] == float

    def test_atr_spec_has_optional_params(self):
        """Verify ATR spec defines optional parameters with defaults."""
        atr_spec = REM_INDICATORS_REGISTRY["atr"]
        assert "length" in atr_spec.optional_params
        param_type, default_value = atr_spec.optional_params["length"]
        assert param_type == int
        assert default_value == 14

    def test_atr_spec_has_calculator(self):
        """Verify ATR spec has a stop calculator function."""
        atr_spec = REM_INDICATORS_REGISTRY["atr"]
        assert callable(atr_spec.stop_calculator)
        assert atr_spec.stop_calculator == _calculate_atr_stop

    def test_registry_contains_bollinger(self):
        """Verify Bollinger indicator is registered."""
        assert "bollinger" in REM_INDICATORS_REGISTRY
        assert REM_INDICATORS_REGISTRY["bollinger"].name == "bollinger"

    def test_bollinger_spec_parameters(self):
        """Verify Bollinger spec defines parameter expectations."""
        boll_spec = REM_INDICATORS_REGISTRY["bollinger"]
        assert boll_spec.required_params == {}
        optional = boll_spec.optional_params
        assert optional["band"] == (str, "auto")
        assert optional["length"] == (int, 20)
        assert optional["std"] == (float, 2.0)
        assert optional["offset"] == (float, 0.0)
        assert optional["column_prefix"] == (str, "bb")

    def test_unknown_indicator_not_in_registry(self):
        """Verify unimplemented indicators are not in registry."""
        # RSI should NOT be in the REM registry (not suitable for stops)
        assert "rsi" not in REM_INDICATORS_REGISTRY
        assert "macd" not in REM_INDICATORS_REGISTRY
        assert "ema" not in REM_INDICATORS_REGISTRY

    def test_registry_only_contains_whitelisted_indicators(self):
        """Verify registry only contains explicitly whitelisted indicators."""
        assert set(REM_INDICATORS_REGISTRY.keys()) == {"atr", "bollinger"}

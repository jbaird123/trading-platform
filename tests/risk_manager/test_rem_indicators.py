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
    _calculate_chandelier_stop,
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

    def test_indicator_specs_do_not_require_intrabar_zoom_by_default(self):
        """REM indicators should not demand intrabar zoom unless opted-in."""
        for spec in REM_INDICATORS_REGISTRY.values():
            assert spec.requires_intrabar_zoom is False

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
        assert set(REM_INDICATORS_REGISTRY.keys()) == {
            "atr",
            "bollinger",
            "chandelier",
        }


class TestChandelierStopCalculator:
    """Tests for Chandelier Stop calculator."""

    def test_chandelier_stop_long_basic(self):
        """Test Chandelier Stop for long position with defaults."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "high": 1.3050,
                "low": 1.2950,
                "close": 1.3020,
                "hhv_22": 1.3100,  # Highest high over 22 periods
                "llv_22": 1.2900,
                "atr_14": 0.0020,  # ATR value
            }
        )
        params: dict[str, object] = {}  # Use all defaults

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = HHV - (ATR * multiplier)
        # = 1.3100 - (0.0020 * 3.0) = 1.3100 - 0.0060 = 1.3040
        assert result == pytest.approx(1.3040, abs=1e-6)

    def test_chandelier_stop_short_basic(self):
        """Test Chandelier Stop for short position with defaults."""
        entry_price = 1.3000
        side = "short"
        current_bar = pd.Series(
            {
                "high": 1.3050,
                "low": 1.2950,
                "close": 1.3020,
                "hhv_22": 1.3100,
                "llv_22": 1.2900,  # Lowest low over 22 periods
                "atr_14": 0.0020,
            }
        )
        params: dict[str, object] = {}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = LLV + (ATR * multiplier)
        # = 1.2900 + (0.0020 * 3.0) = 1.2900 + 0.0060 = 1.2960
        assert result == pytest.approx(1.2960, abs=1e-6)

    def test_chandelier_stop_custom_multiplier(self):
        """Test Chandelier Stop with custom ATR multiplier."""
        entry_price = 100.0
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_22": 105.0,
                "llv_22": 95.0,
                "atr_14": 2.0,
            }
        )
        params = {"multiplier": 2.5}  # Custom multiplier

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = 105.0 - (2.0 * 2.5) = 105.0 - 5.0 = 100.0
        assert result == pytest.approx(100.0, abs=1e-6)

    def test_chandelier_stop_custom_length(self):
        """Test Chandelier Stop with custom lookback period."""
        entry_price = 1.2000
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_50": 1.2500,  # 50-period HHV instead of 22
                "llv_50": 1.1500,
                "atr_14": 0.0015,
            }
        )
        params = {"length": 50}  # Custom length

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = 1.2500 - (0.0015 * 3.0) = 1.2500 - 0.0045 = 1.2455
        assert result == pytest.approx(1.2455, abs=1e-6)

    def test_chandelier_stop_custom_atr_length(self):
        """Test Chandelier Stop with custom ATR period."""
        entry_price = 1.1000
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_22": 1.1200,
                "llv_22": 1.0800,
                "atr_20": 0.0025,  # 20-period ATR instead of 14
            }
        )
        params = {"atr_length": 20}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = 1.1200 - (0.0025 * 3.0) = 1.1200 - 0.0075 = 1.1125
        assert result == pytest.approx(1.1125, abs=1e-6)

    def test_chandelier_stop_all_custom_params(self):
        """Test Chandelier Stop with all custom parameters."""
        entry_price = 50.0
        side = "short"
        current_bar = pd.Series(
            {
                "hhv_30": 55.0,
                "llv_30": 45.0,
                "atr_10": 1.5,
            }
        )
        params = {
            "multiplier": 4.0,
            "length": 30,
            "atr_length": 10,
        }

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Stop = LLV + (ATR * multiplier)
        # = 45.0 + (1.5 * 4.0) = 45.0 + 6.0 = 51.0
        assert result == pytest.approx(51.0, abs=1e-6)

    def test_chandelier_stop_uses_generic_atr_column(self):
        """Test that chandelier falls back to generic 'atr' column."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_22": 1.3100,
                "atr": 0.0020,  # Generic ATR column (no length suffix)
            }
        )
        params: dict[str, object] = {}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Should use generic 'atr' column
        # Stop = 1.3100 - (0.0020 * 3.0) = 1.3040
        assert result == pytest.approx(1.3040, abs=1e-6)

    def test_chandelier_stop_prefers_specific_atr_column(self):
        """Test chandelier prefers atr_{length} over generic atr."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_22": 1.3100,
                "atr_14": 0.0020,  # Specific ATR
                "atr": 0.0010,  # Should be ignored
            }
        )
        params: dict[str, object] = {}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        # Should use atr_14, not generic atr
        # Stop = 1.3100 - (0.0020 * 3.0) = 1.3040
        assert result == pytest.approx(1.3040, abs=1e-6)

    def test_chandelier_stop_supports_uppercase_hhv(self):
        """Test chandelier supports uppercase HHV column name."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "HHV_22": 1.3100,  # Uppercase variant
                "atr_14": 0.0020,
            }
        )
        params: dict[str, object] = {}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.3040, abs=1e-6)

    def test_chandelier_stop_supports_uppercase_llv(self):
        """Test chandelier supports uppercase LLV column name."""
        entry_price = 1.3000
        side = "short"
        current_bar = pd.Series(
            {
                "LLV_22": 1.2900,  # Uppercase variant
                "atr_14": 0.0020,
            }
        )
        params: dict[str, object] = {}

        result = _calculate_chandelier_stop(entry_price, side, current_bar, params)

        assert result == pytest.approx(1.2960, abs=1e-6)

    def test_chandelier_stop_missing_hhv_raises_error(self):
        """Test missing HHV column raises KeyError for long."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "close": 1.3020,
                "atr_14": 0.0020,
                # Missing hhv_22!
            }
        )
        params: dict[str, object] = {}

        with pytest.raises(KeyError, match="HHV indicator not found"):
            _calculate_chandelier_stop(entry_price, side, current_bar, params)

    def test_chandelier_stop_missing_llv_raises_error(self):
        """Test missing LLV column raises KeyError for short."""
        entry_price = 1.3000
        side = "short"
        current_bar = pd.Series(
            {
                "close": 1.3020,
                "atr_14": 0.0020,
                # Missing llv_22!
            }
        )
        params: dict[str, object] = {}

        with pytest.raises(KeyError, match="LLV indicator not found"):
            _calculate_chandelier_stop(entry_price, side, current_bar, params)

    def test_chandelier_stop_missing_atr_raises_error(self):
        """Test missing ATR column raises KeyError."""
        entry_price = 1.3000
        side = "long"
        current_bar = pd.Series(
            {
                "hhv_22": 1.3100,
                "llv_22": 1.2900,
                # Missing atr_14!
            }
        )
        params: dict[str, object] = {}

        with pytest.raises(KeyError, match="ATR indicator not found"):
            _calculate_chandelier_stop(entry_price, side, current_bar, params)

    def test_chandelier_stop_invalid_side_raises_error(self):
        """Test invalid side parameter raises ValueError."""
        entry_price = 1.3000
        side = "sideways"  # Invalid!
        current_bar = pd.Series(
            {
                "hhv_22": 1.3100,
                "llv_22": 1.2900,
                "atr_14": 0.0020,
            }
        )
        params: dict[str, object] = {}

        with pytest.raises(ValueError, match="Invalid side"):
            _calculate_chandelier_stop(entry_price, side, current_bar, params)

    def test_chandelier_registry_entry(self):
        """Test Chandelier Stop is properly registered."""
        assert "chandelier" in REM_INDICATORS_REGISTRY
        chandelier_spec = REM_INDICATORS_REGISTRY["chandelier"]

        assert chandelier_spec.name == "chandelier"
        assert "Chandelier" in chandelier_spec.description
        assert chandelier_spec.stop_calculator == _calculate_chandelier_stop
        assert chandelier_spec.requires_prior_bar is True

    def test_chandelier_registry_params(self):
        """Test Chandelier spec defines correct parameters."""
        chandelier_spec = REM_INDICATORS_REGISTRY["chandelier"]

        # No required params (all are optional with defaults)
        assert chandelier_spec.required_params == {}

        # Optional params with defaults
        optional = chandelier_spec.optional_params
        assert optional["multiplier"] == (float, 3.0)
        assert optional["length"] == (int, 22)
        assert optional["atr_length"] == (int, 14)

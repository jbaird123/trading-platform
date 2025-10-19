"""Tests for REM Pydantic Configuration Models.

Tests strict validation of REM configurations using Pydantic models.
These tests ensure that:
1. Valid configs pass validation
2. Invalid configs fail with clear error messages
3. Extra/unknown fields are rejected (extra="forbid")
4. Missing required fields are caught
5. Old atr_multiple format is rejected
"""

import pytest
from pydantic import ValidationError

from trading_platform.risk_manager.models import (
    ATRStopParams,
    FixedPipStop,
    IndicatorStop,
    REMConfig,
)


class TestFixedPipStop:
    """Tests for FixedPipStop model."""

    def test_valid_fixed_pip_stop(self):
        """Test valid fixed pip stop-loss configuration."""
        data = {
            "type": "fixed_pips",
            "pips": 20
        }

        stop = FixedPipStop(**data)

        assert stop.type == "fixed_pips"
        assert stop.pips == 20

    def test_fixed_pip_stop_float_pips(self):
        """Test fixed pip stop with float pips value."""
        data = {
            "type": "fixed_pips",
            "pips": 15.5
        }

        stop = FixedPipStop(**data)

        assert stop.pips == 15.5

    def test_fixed_pip_stop_zero_pips_rejected(self):
        """Test that zero pips is rejected."""
        data = {
            "type": "fixed_pips",
            "pips": 0
        }

        with pytest.raises(ValidationError, match="greater than 0"):
            FixedPipStop(**data)

    def test_fixed_pip_stop_negative_pips_rejected(self):
        """Test that negative pips are rejected."""
        data = {
            "type": "fixed_pips",
            "pips": -10
        }

        with pytest.raises(ValidationError, match="greater than 0"):
            FixedPipStop(**data)

    def test_fixed_pip_stop_missing_pips_rejected(self):
        """Test that missing pips field is rejected."""
        data = {
            "type": "fixed_pips"
            # Missing pips!
        }

        with pytest.raises(ValidationError, match="pips"):
            FixedPipStop(**data)

    def test_fixed_pip_stop_extra_field_rejected(self):
        """Test that extra fields are rejected."""
        data = {
            "type": "fixed_pips",
            "pips": 20,
            "unknown_field": "value"
        }

        with pytest.raises(ValidationError, match="extra"):
            FixedPipStop(**data)


class TestATRStopParams:
    """Tests for ATRStopParams model."""

    def test_valid_atr_params(self):
        """Test valid ATR parameters."""
        data = {
            "length": 14,
            "multiplier": 2.0
        }

        params = ATRStopParams(**data)

        assert params.length == 14
        assert params.multiplier == 2.0

    def test_atr_params_uses_default_length(self):
        """Test ATR params with default length."""
        data = {
            "multiplier": 2.5
        }

        params = ATRStopParams(**data)

        assert params.length == 14  # Default
        assert params.multiplier == 2.5

    def test_atr_params_missing_multiplier_rejected(self):
        """Test that missing multiplier is rejected."""
        data = {
            "length": 20
            # Missing required multiplier!
        }

        with pytest.raises(ValidationError, match="multiplier"):
            ATRStopParams(**data)

    def test_atr_params_zero_multiplier_rejected(self):
        """Test that zero multiplier is rejected."""
        data = {
            "multiplier": 0,
            "length": 14
        }

        with pytest.raises(ValidationError, match="greater than 0"):
            ATRStopParams(**data)

    def test_atr_params_negative_multiplier_rejected(self):
        """Test that negative multiplier is rejected."""
        data = {
            "multiplier": -1.5,
            "length": 14
        }

        with pytest.raises(ValidationError, match="greater than 0"):
            ATRStopParams(**data)

    def test_atr_params_zero_length_rejected(self):
        """Test that zero length is rejected."""
        data = {
            "multiplier": 2.0,
            "length": 0
        }

        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ATRStopParams(**data)

    def test_atr_params_extra_field_rejected(self):
        """Test that extra fields are rejected."""
        data = {
            "multiplier": 2.0,
            "length": 14,
            "smoothing": "ema"  # Not a valid field!
        }

        with pytest.raises(ValidationError, match="extra"):
            ATRStopParams(**data)


class TestIndicatorStop:
    """Tests for IndicatorStop model."""

    def test_valid_atr_indicator_stop(self):
        """Test valid ATR indicator stop-loss."""
        data = {
            "type": "indicator",
            "indicator": "atr",
            "params": {
                "length": 14,
                "multiplier": 2.0
            }
        }

        stop = IndicatorStop(**data)

        assert stop.type == "indicator"
        assert stop.indicator == "atr"
        assert isinstance(stop.params, ATRStopParams)
        assert stop.params.length == 14
        assert stop.params.multiplier == 2.0

    def test_unimplemented_indicator_rejected(self):
        """Test that unimplemented indicators fail validation."""
        data = {
            "type": "indicator",
            "indicator": "rsi",  # NOT in whitelist!
            "params": {"length": 14}
        }

        with pytest.raises(ValidationError, match="Input should be 'atr'"):
            IndicatorStop(**data)

    def test_indicator_stop_missing_params_rejected(self):
        """Test that missing params field is rejected."""
        data = {
            "type": "indicator",
            "indicator": "atr"
            # Missing params!
        }

        with pytest.raises(ValidationError, match="params"):
            IndicatorStop(**data)

    def test_indicator_stop_invalid_params_rejected(self):
        """Test that invalid params for indicator are rejected."""
        data = {
            "type": "indicator",
            "indicator": "atr",
            "params": {
                "length": 14
                # Missing required multiplier!
            }
        }

        with pytest.raises(ValidationError, match="multiplier"):
            IndicatorStop(**data)

    def test_indicator_stop_extra_field_rejected(self):
        """Test that extra fields are rejected."""
        data = {
            "type": "indicator",
            "indicator": "atr",
            "params": {
                "multiplier": 2.0,
                "length": 14
            },
            "trailing": True  # Not a valid field!
        }

        with pytest.raises(ValidationError, match="extra"):
            IndicatorStop(**data)


class TestREMConfig:
    """Tests for REMConfig model."""

    def test_valid_fixed_pip_config(self):
        """Test valid fixed pip REM configuration."""
        data = {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            }
        }

        config = REMConfig(**data)

        assert isinstance(config.stop_loss, FixedPipStop)
        assert config.stop_loss.pips == 20
        assert config.take_profit is None

    def test_valid_atr_indicator_config(self):
        """Test valid ATR indicator REM configuration."""
        data = {
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {
                    "length": 14,
                    "multiplier": 2.0
                }
            }
        }

        config = REMConfig(**data)

        assert isinstance(config.stop_loss, IndicatorStop)
        assert config.stop_loss.indicator == "atr"

    def test_config_with_stop_and_tp(self):
        """Test config with both stop-loss and take-profit."""
        data = {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            },
            "take_profit": {
                "type": "fixed_pips",
                "pips": 40
            }
        }

        config = REMConfig(**data)

        assert config.stop_loss.pips == 20
        assert config.take_profit.pips == 40

    def test_config_with_mixed_types(self):
        """Test config with fixed stop and ATR take-profit."""
        data = {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            },
            "take_profit": {
                "type": "indicator",
                "indicator": "atr",
                "params": {
                    "multiplier": 3.0
                }
            }
        }

        config = REMConfig(**data)

        assert isinstance(config.stop_loss, FixedPipStop)
        assert isinstance(config.take_profit, IndicatorStop)

    def test_config_with_name_and_version(self):
        """Test config with optional name and version fields."""
        data = {
            "name": "Conservative ATR",
            "version": "1.0",
            "stop_loss": {
                "type": "indicator",
                "indicator": "atr",
                "params": {
                    "multiplier": 2.0
                }
            }
        }

        config = REMConfig(**data)

        assert config.name == "Conservative ATR"
        assert config.version == "1.0"

    def test_config_missing_stop_loss_rejected(self):
        """Test that missing stop_loss is rejected."""
        data = {
            "take_profit": {
                "type": "fixed_pips",
                "pips": 40
            }
        }

        with pytest.raises(ValidationError, match="stop_loss"):
            REMConfig(**data)

    def test_config_extra_field_rejected(self):
        """Test that extra/unknown fields are rejected."""
        data = {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            },
            "breakeven": {  # DynamicREM feature, not in basic REM!
                "trigger": 1.0
            }
        }

        with pytest.raises(ValidationError, match="extra"):
            REMConfig(**data)

    def test_old_atr_multiple_format_rejected(self):
        """Test that old atr_multiple format is rejected."""
        # This is the critical test - ensure old format doesn't work!
        data = {
            "stop_loss": {
                "atr_multiple": 2.0,  # Old format
                "atr_length": 14
            }
        }

        with pytest.raises(ValidationError):
            REMConfig(**data)

    def test_config_dict_export(self):
        """Test that config can be exported to dict."""
        data = {
            "stop_loss": {
                "type": "fixed_pips",
                "pips": 20
            }
        }

        config = REMConfig(**data)
        exported = config.model_dump()

        assert exported["stop_loss"]["type"] == "fixed_pips"
        assert exported["stop_loss"]["pips"] == 20

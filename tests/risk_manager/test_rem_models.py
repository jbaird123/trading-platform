"""Tests for the REM Pydantic configuration models."""

import pytest
from pydantic import ValidationError
from trading_platform.risk_manager import rem_indicators
from trading_platform.risk_manager.models import REMConfig


class TestREMConfigValidRules:
    """Ensure the new rule dialect validates supported rule shapes."""

    def test_rem_config_accepts_absolute_rule(self):
        config = REMConfig(stop_loss={"type": "absolute", "price": 1.2050})

        assert config.stop_loss.type == "absolute"
        assert config.stop_loss.price == 1.2050

    def test_rem_config_accepts_offset_rule(self):
        config = REMConfig(stop_loss={"type": "offset", "price_offset": 0.002})

        assert config.stop_loss.type == "offset"
        assert config.stop_loss.price_offset == 0.002

    def test_rem_config_accepts_fixed_pips_rule(self):
        config = REMConfig(stop_loss={"type": "fixed_pips", "pips": 25.0})

        assert config.stop_loss.type == "fixed_pips"
        assert config.stop_loss.pips == 25.0

    def test_rem_config_accepts_indicator_rule(self, monkeypatch):
        monkeypatch.setattr(
            rem_indicators,
            "REM_INDICATORS_REGISTRY",
            {
                "atr": rem_indicators.REMIndicatorSpec(
                    name="atr",
                    description="ATR",
                    required_params={"multiplier": float},
                    optional_params={"length": (int, 14)},
                    stop_calculator=lambda *args, **kwargs: 0.0,
                )
            },
        )

        config = REMConfig(
            stop_loss={
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 2.0, "length": 21},
            }
        )

        assert config.stop_loss.type == "indicator"
        assert config.stop_loss.indicator == "atr"
        assert config.stop_loss.params["multiplier"] == 2.0
        assert config.stop_loss.params["length"] == 21

    def test_rem_config_accepts_bollinger_indicator(self):
        config = REMConfig(
            stop_loss={
                "type": "indicator",
                "indicator": "bollinger",
                "params": {"band": "lower", "offset": 0.0005},
            }
        )

        assert config.stop_loss.type == "indicator"
        assert config.stop_loss.indicator == "bollinger"
        assert config.stop_loss.params["band"] == "lower"
        assert config.stop_loss.params["offset"] == 0.0005

    def test_rem_config_accepts_reference_rule(self):
        config = REMConfig(
            stop_loss={
                "type": "reference",
                "reference_point": "context.order_block_low",
                "offset": {"type": "fixed_pips", "pips": 5.0},
            }
        )

        assert config.stop_loss.type == "reference"
        assert config.stop_loss.reference_point == "context.order_block_low"
        assert config.stop_loss.offset.type == "fixed_pips"
        assert config.stop_loss.offset.pips == 5.0

    def test_rem_config_accepts_trailing_stop_rule(self):
        config = REMConfig(
            stop_loss={"type": "fixed_pips", "pips": 20.0},
            trailing_stop={
                "distance": {"type": "offset", "price_offset": 0.0015},
                "step": 0.0,
                "update": "bar",
            },
        )

        assert config.trailing_stop is not None
        assert config.trailing_stop.distance.type == "offset"
        assert config.trailing_stop.distance.price_offset == 0.0015


class TestREMConfigInvalidRules:
    """Ensure unsupported or malformed rule payloads fail loudly."""

    def test_rem_config_rejects_negative_distance(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            REMConfig(stop_loss={"type": "offset", "price_offset": -0.5})

    def test_rem_config_rejects_missing_distance_fields(self):
        with pytest.raises(ValidationError, match="Field required"):
            REMConfig(stop_loss={"type": "offset"})

    def test_rem_config_rejects_unknown_indicator(self, monkeypatch):
        monkeypatch.setattr(
            rem_indicators,
            "REM_INDICATORS_REGISTRY",
            {"atr": rem_indicators.REM_INDICATORS_REGISTRY["atr"]},
        )

        with pytest.raises(ValidationError, match="Unknown REM indicator"):
            REMConfig(
                stop_loss={
                    "type": "indicator",
                    "indicator": "bollinger",
                    "params": {"multiplier": 2.0},
                }
            )

    def test_rem_config_rejects_legacy_atr_multiple(self):
        with pytest.raises(ValidationError, match="type"):
            REMConfig(stop_loss={"atr_multiple": 2.0})

    def test_rem_config_rejects_invalid_trailing_update(self):
        with pytest.raises(ValidationError, match="update"):
            REMConfig(
                stop_loss={"type": "fixed_pips", "pips": 20.0},
                trailing_stop={
                    "distance": {"type": "fixed_pips", "pips": 10.0},
                    "update": "minute",
                },
            )

    def test_rem_config_rejects_negative_trailing_step(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            REMConfig(
                stop_loss={"type": "fixed_pips", "pips": 20.0},
                trailing_stop={
                    "distance": {"type": "offset", "price_offset": 0.001},
                    "step": -0.1,
                },
            )


class TestIndicatorRegistryIntegration:
    """Tie indicator validation back to the registry."""

    def test_indicator_stop_uses_registry(self, monkeypatch):
        stub = rem_indicators.REMIndicatorSpec(
            name="atr",
            description="ATR",
            required_params={"multiplier": float},
            optional_params={},
            stop_calculator=lambda *args, **kwargs: 0.0,
        )
        monkeypatch.setattr(rem_indicators, "REM_INDICATORS_REGISTRY", {"atr": stub})

        config = REMConfig(
            stop_loss={
                "type": "indicator",
                "indicator": "atr",
                "params": {"multiplier": 1.5},
            }
        )

        assert config.stop_loss.params["multiplier"] == 1.5

    def test_indicator_stop_rejects_unregistered_indicator(self, monkeypatch):
        monkeypatch.setattr(rem_indicators, "REM_INDICATORS_REGISTRY", {})

        with pytest.raises(ValidationError, match="Unknown REM indicator"):
            REMConfig(
                stop_loss={
                    "type": "indicator",
                    "indicator": "atr",
                    "params": {"multiplier": 1.5},
                }
            )


class TestREMConfigSerialization:
    """Ensure the model round-trips cleanly."""

    def test_rem_config_serializes_cleanly(self, monkeypatch):
        monkeypatch.setattr(
            rem_indicators,
            "REM_INDICATORS_REGISTRY",
            rem_indicators.REM_INDICATORS_REGISTRY,
        )
        config = REMConfig(
            name="Trailing Strategy",
            stop_loss={"type": "fixed_pips", "pips": 25.0},
            take_profit={"type": "offset", "price_offset": 0.004},
            trailing_stop={
                "distance": {"type": "fixed_pips", "pips": 15.0},
                "update": "bar",
            },
        )

        dumped = config.model_dump()

        assert dumped["stop_loss"]["type"] == "fixed_pips"
        assert dumped["take_profit"]["type"] == "offset"
        assert dumped["trailing_stop"]["distance"]["type"] == "fixed_pips"

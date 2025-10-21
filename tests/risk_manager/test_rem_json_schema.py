"""Pydantic JSON-schema alignment tests for REM configurations."""

from trading_platform.risk_manager.models import DynamicREMConfig, REMConfig


def test_rem_config_json_schema_exposes_rule_types():
    schema = REMConfig.model_json_schema()
    stop_schema = schema["properties"]["stop_loss"]
    mapping = stop_schema["discriminator"]["mapping"]
    assert set(mapping.keys()) == {
        "absolute",
        "offset",
        "fixed_pips",
        "indicator",
        "reference",
    }

    trailing_def = schema["$defs"]["TrailingStopRule"]["properties"]["distance"]
    trailing_mapping = trailing_def["discriminator"]["mapping"]
    assert set(trailing_mapping.keys()) == {"offset", "fixed_pips"}


def test_dynamic_rem_config_json_schema_exposes_trailing_distance():
    schema = DynamicREMConfig.model_json_schema()
    trailing_def = schema["$defs"]["DynamicTrailingStopRule"]["properties"]["distance"]
    mapping = trailing_def["discriminator"]["mapping"]
    assert set(mapping.keys()) == {"offset", "atr"}

    partial_def = schema["$defs"]["PartialExitRule"]["properties"]
    assert partial_def["r_multiple"]["minimum"] == 0
    assert partial_def["fraction"]["maximum"] == 1

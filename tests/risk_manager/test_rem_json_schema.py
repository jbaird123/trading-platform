"""Pydantic JSON-schema alignment tests for REM configurations."""

from trading_platform.risk_manager.models import (
    DynamicREMConfig,
    REMConfig,
)


def test_rem_config_json_schema_exposes_rule_types():
    schema = REMConfig.model_json_schema()

    assert schema["title"] == "REMConfig"

    stop_schema = schema["properties"]["stop_loss"]
    type_enum = stop_schema["properties"]["type"]["enum"]
    assert {"absolute", "offset", "fixed_pips", "indicator", "reference"} == set(
        type_enum
    )

    trailing_schema = schema["properties"]["trailing_stop"]["properties"]
    distance_schema = trailing_schema["properties"]["distance"]["properties"]["type"]
    assert {"offset", "fixed_pips"} == set(distance_schema["enum"])


def test_dynamic_rem_config_json_schema_exposes_trailing_distance():
    schema = DynamicREMConfig.model_json_schema()

    trailing = schema["properties"]["trailing_stop"]["properties"]
    distance_type = trailing["properties"]["distance"]["properties"]["type"]
    assert {"offset", "atr"} == set(distance_type["enum"])

    partial_exit = schema["properties"]["partial_exits"]["items"]["properties"]
    assert partial_exit["r_multiple"]["minimum"] == 0
    assert partial_exit["fraction"]["maximum"] == 1

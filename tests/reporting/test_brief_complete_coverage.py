from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from trading_platform.reporting.brief import (
    _lookup_schema,
    _round_currency,
    _round_price,
    _schema_node_type,
    generate_brief,
)


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_with_empty_signals_file(
    mock_read_parquet, mock_exists, tmp_path
):
    """Verify brief generation handles an empty signals file gracefully."""
    mock_read_parquet.return_value = pd.DataFrame(columns=["signal"])
    signals_path = tmp_path / "signals.parquet"
    signals_path.touch()

    brief = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        signals_path=str(signals_path),
    )

    assert "signal_quality_analysis" in brief
    assert brief["signal_quality_analysis"]["signal_persistence_pct"] == 0.0


def test_generate_brief_with_prepopulated_field_definitions():
    """Verify brief generation uses provided field_definitions."""
    custom_defs = {"meta.run_id": "Custom Run ID"}
    brief = generate_brief(
        meta={"run_id": "test-run"},
        params={},
        trades=[],
        initial_cash=10000,
        field_definitions=custom_defs,
    )

    assert brief["field_definitions"] == custom_defs


def test_generate_brief_with_empty_checksums_dict():
    """Verify an empty checksums dictionary is handled correctly."""
    brief = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        config_snapshot=None,
        instrument_definitions=None,
    )

    assert "checksums" not in brief


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_handles_invalid_signals_dataframe(
    mock_read_parquet, mock_exists
):
    """Test that a signal DataFrame without a 'signal' column raises ValueError."""
    mock_read_parquet.return_value = pd.DataFrame({"other_column": [1, 2, 3]})
    with pytest.raises(ValueError, match="must contain 'signal' column"):
        generate_brief(
            meta={},
            params={},
            trades=[],
            initial_cash=10000,
            signals_path="dummy.parquet",
        )


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_handles_invalid_signals_type(mock_read_parquet, mock_exists):
    """Test that providing an invalid type for signals raises ValueError."""
    mock_read_parquet.return_value = [1, 2, 3]
    with pytest.raises(ValueError, match="must be pandas DataFrame or Series"):
        generate_brief(
            meta={},
            params={},
            trades=[],
            initial_cash=10000,
            signals_path="dummy.parquet",
        )


def test_schema_node_type():
    assert _schema_node_type({"type": "string"}) == "string"
    assert _schema_node_type({"type": ["string", "null"]}) == "null/string"
    assert _schema_node_type({}) == "object"


def test_lookup_schema():
    schema = {
        "properties": {
            "foo": {"properties": {"bar": {"type": "string", "description": "a bar"}}},
            "baz": {"type": "object", "additionalProperties": {"type": "integer"}},
        }
    }
    assert _lookup_schema(schema, ["foo", "bar"]) == {
        "type": "string",
        "description": "a bar",
    }
    assert _lookup_schema(schema, ["foo", "qux"]) is None
    assert _lookup_schema(schema, ["baz", "any"]) == {"type": "integer"}
    assert _lookup_schema(schema, ["foo"]) is not None


def test_round_currency():
    assert _round_currency(None) == 0.0
    assert _round_currency(1.234) == 1.23
    assert _round_currency(1.235) == 1.24


def test_round_price():
    assert _round_price(None) is None
    assert _round_price(1.23456) == 1.2346


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_with_signals_none(mock_read_parquet, mock_exists):
    mock_read_parquet.return_value = None
    brief = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        signals_path="dummy.parquet",
    )
    assert brief["signal_quality_analysis"]["signal_persistence_pct"] == 0.0


def test_generate_brief_with_empty_checksums():
    brief = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        config_snapshot=None,
        instrument_definitions=None,
    )
    assert "checksums" not in brief

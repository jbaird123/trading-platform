# Validates: [JSON-11.1], [JSON-11.2], [JSON-11.4], [JSON-11.5]
from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore
import pytest
from trading_platform.reporting.brief import generate_brief

SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs/schemas/brief.schema.json"


@pytest.fixture(scope="module")
def brief_schema():
    """Loads the Brief JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_minimal_brief_validates_against_schema(brief_schema):
    """Tests that a minimal, valid brief passes schema validation."""
    # Arrange: Create a minimal brief
    brief = generate_brief(
        meta={"run_id": "test_run", "strategy_name": "TestStrat"},
        params={"param1": 10},
        trades=[],
        initial_cash=100000.0,
    )

    # Add minimal data_quality fields to satisfy schema
    brief["data_quality"] = {
        "loader_flags": [],
        "index_monotonic_increasing": True,
        "duplicate_bars_count": 0,
        "nan_counts": {},
        "has_nans": False,
    }

    # Add minimal checksums fields to satisfy schema
    brief["checksums"] = {
        "config_snapshot_hash": "dummy_config_hash",
        "instrument_defs_hash": "dummy_instrument_hash",
    }

    # Add minimal field_definitions to satisfy schema (string values only)
    brief["field_definitions"] = {
        "meta": "Metadata about the run.",
        "strategy_params": "Strategy parameters.",
        "overall_performance": "Overall performance metrics.",
        "risk_snapshot": "Key risk metrics.",
        "equity_stats": "Equity curve statistics.",
        "distribution": "Trade PnL distribution.",
        "streaks": "Win/loss streaks.",
        "holding_time": "Trade holding time metrics.",
        "costs": "Trading costs.",
        "trades": "List of executed trades.",
    }

    # Add minimal equity_stats curves to satisfy schema
    brief["equity_stats"]["equity_curve"] = [
        ["2023-01-01T00:00:00", 100000.0],
        ["2023-01-02T00:00:00", 100010.0],
    ]
    brief["equity_stats"]["drawdown_curve"] = [
        ["2023-01-01T00:00:00", 0.0],
        ["2023-01-02T00:00:00", -5.0],
    ]

    # Act & Assert: Validate against the schema
    try:
        jsonschema.validate(instance=brief, schema=brief_schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Minimal brief failed validation: {e}")

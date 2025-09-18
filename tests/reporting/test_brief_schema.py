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

    # Add minimal field_definitions to satisfy schema
    brief["field_definitions"] = {
        "meta": {"description": "Metadata about the run.", "type": "object"},
        "strategy_params": {"description": "Strategy parameters.", "type": "object"},
        "overall_performance": {
            "description": "Overall performance metrics.",
            "type": "object",
        },
        "risk_snapshot": {"description": "Key risk metrics.", "type": "object"},
        "equity_stats": {"description": "Equity curve statistics.", "type": "object"},
        "distribution": {"description": "Trade PnL distribution.", "type": "object"},
        "streaks": {"description": "Win/loss streaks.", "type": "object"},
        "holding_time": {
            "description": "Trade holding time metrics.",
            "type": "object",
        },
        "costs": {"description": "Trading costs.", "type": "object"},
        "trades": {"description": "List of executed trades.", "type": "array"},
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

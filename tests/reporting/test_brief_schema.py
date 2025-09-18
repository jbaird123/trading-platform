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

    # Act & Assert: Validate against the schema
    try:
        jsonschema.validate(instance=brief, schema=brief_schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Minimal brief failed validation: {e}")

import json
from pathlib import Path
from typing import Any


def _check_descriptions_recursive(obj: Any, path: str):
    """
    Recursively traverses the schema and asserts a description exists for every
    property.
    """
    if isinstance(obj, dict):
        # If it's an object with properties, check each property
        if obj.get("type") == "object" and "properties" in obj:
            for prop, prop_schema in obj["properties"].items():
                new_path = f"{path}.{prop}" if path else prop
                assert (
                    "description" in prop_schema
                ), f"Missing description for: {new_path}"
                assert isinstance(
                    prop_schema["description"], str
                ), f"Description must be a string for: {new_path}"
                assert (
                    len(prop_schema["description"]) > 0
                ), f"Description cannot be empty for: {new_path}"
                # Recurse into the property's schema
                _check_descriptions_recursive(prop_schema, new_path)

        # If it's an array of objects, check the item schema
        if obj.get("type") == "array" and "items" in obj:
            new_path = f"{path}[]"
            _check_descriptions_recursive(obj["items"], new_path)


def test_all_brief_schema_fields_have_descriptions():
    """
    Validates that every field in the brief.schema.json has a description.
    This is a meta-test to enforce schema quality.
    """
    schema_path = Path("docs/schemas/brief.schema.json")
    assert schema_path.exists(), "brief.schema.json not found"

    schema = json.loads(schema_path.read_text())
    _check_descriptions_recursive(schema, "")

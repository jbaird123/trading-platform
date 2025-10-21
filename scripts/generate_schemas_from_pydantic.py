#!/usr/bin/env python3
"""Generate JSON schemas from Pydantic models.

This ensures JSON schemas stay in sync with Pydantic models (single source of truth).

Usage:
    poetry run python scripts/generate_schemas_from_pydantic.py

Generated schemas are written to docs/schemas/ and should be committed to git.
"""

import json
from pathlib import Path

from trading_platform.core.config import FeatureConfig, RunConfig
from trading_platform.strategy.models import StrategyConfig


def generate_schema(model_class, output_path: Path) -> None:
    """Generate JSON schema from Pydantic model.

    Args:
        model_class: Pydantic BaseModel class
        output_path: Path where JSON schema will be written
    """
    # Generate JSON schema using Pydantic's built-in method
    schema = model_class.model_json_schema()

    # Write to file with nice formatting
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"✓ Generated {output_path.name} ({len(json.dumps(schema))} bytes)")


def main() -> None:
    """Generate all JSON schemas from Pydantic models."""
    # Ensure schemas directory exists
    schemas_dir = Path(__file__).parent.parent / "docs" / "schemas"
    schemas_dir.mkdir(exist_ok=True, parents=True)

    print("Generating JSON schemas from Pydantic models...")
    print("=" * 80)

    # Generate schemas for each model
    # Order matters - dependencies should come first
    schemas_to_generate = [
        (FeatureConfig, "feature_config.schema.json"),
        (RunConfig, "run_config.schema.json"),
        (StrategyConfig, "strategy.schema.json"),
    ]

    for model_class, filename in schemas_to_generate:
        output_path = schemas_dir / filename
        generate_schema(model_class, output_path)

    print("=" * 80)
    print(f"✅ Generated {len(schemas_to_generate)} schemas in {schemas_dir}")
    print()
    print("Note: These schemas are auto-generated from Pydantic models.")
    print("      DO NOT edit manually - edit the Pydantic models instead.")
    print("      Re-run this script after changing Pydantic models.")


if __name__ == "__main__":
    main()

# Migrate to Pydantic as Single Source of Truth

## Status: In Progress

## Objective

Make Pydantic models the single source of truth for all configuration schemas, eliminating manual JSON schema maintenance while preserving all functionality (validation, brief generation, IDE support).

## Current State

### What Has Pydantic + `extra="forbid"`:
- ✅ REM configs (REMConfig, FixedPipStop, IndicatorStop)
- ✅ RunConfig model itself (just added)
- ✅ FeatureConfig (just added)

### What Still Uses `dict[str, Any]` (No Validation):
- ❌ Strategy configs
- ❌ RMM configs
- ❌ Nested configs in RunConfig (strategy, rem_config, rmm_config fields)

### JSON Schema Dependencies Found:
1. **brief.py** - Extracts field descriptions for brief generation (**CRITICAL**)
2. **strategy/yaml_strategy.py** - Validates strategy configs
3. **regime_market_manager/engine.py** + **config.py** - Validates RMM configs
4. **risk_manager/__init__.py** - Validates dynamic REM configs

## Migration Strategy

### Phase 1: Infrastructure (2-3 hours)

#### Step 1.1: Create Schema Generator Script
**File**: `scripts/generate_schemas_from_pydantic.py`

```python
#!/usr/bin/env python3
"""Generate JSON schemas from Pydantic models.

This ensures JSON schemas stay in sync with Pydantic models (single source of truth).
"""

from pathlib import Path
import json

from trading_platform.core.config import RunConfig, FeatureConfig
from trading_platform.risk_manager.models import REMConfig
# Add more as they're migrated

def generate_schema(model_class, output_path: Path):
    """Generate JSON schema from Pydantic model."""
    schema = model_class.model_json_schema()

    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2)

    print(f"✓ Generated {output_path.name}")

def main():
    schemas_dir = Path("docs/schemas")
    schemas_dir.mkdir(exist_ok=True)

    # Generate schemas (currently only REMConfig requires a JSON export)
    generate_schema(REMConfig, schemas_dir / "rem.schema.json")

    print("\n✅ Schema generated from Pydantic models")

if __name__ == "__main__":
    main()
```

#### Step 1.2: Create Description Extractor for Brief
**File**: `src/trading_platform/reporting/pydantic_descriptions.py`

```python
"""Extract field descriptions from Pydantic models for brief generation."""

from typing import Any
from pydantic import BaseModel

def get_field_descriptions(model_class: type[BaseModel]) -> dict[str, str]:
    """Extract all field descriptions from a Pydantic model.

    Returns dict mapping field paths to descriptions.
    Example: {"user_id": "Identifier for the user...", ...}
    """
    descriptions = {}

    for field_name, field_info in model_class.model_fields.items():
        if field_info.description:
            descriptions[field_name] = field_info.description

    return descriptions

def get_nested_descriptions(model_class: type[BaseModel], prefix: str = "") -> dict[str, str]:
    """Recursively extract descriptions including nested models.

    Returns dict with dot-notation paths.
    Example: {"strategy.name": "Strategy name...", ...}
    """
    descriptions = {}

    for field_name, field_info in model_class.model_fields.items():
        full_path = f"{prefix}.{field_name}" if prefix else field_name

        if field_info.description:
            descriptions[full_path] = field_info.description

        # Handle nested Pydantic models
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            nested = get_nested_descriptions(annotation, full_path)
            descriptions.update(nested)

    return descriptions
```

### Phase 2: Update Brief Generation (1-2 hours)

#### Step 2.1: Update brief.py to Use Pydantic Descriptions

**File**: `src/trading_platform/reporting/brief.py`

**Change from:**
```python
# Line 972
schema = json.loads(SCHEMA_PATH.read_text())
# Extract descriptions from schema...
```

**Change to:**
```python
from trading_platform.reporting.pydantic_descriptions import get_nested_descriptions
from trading_platform.core.config import RunConfig

# Extract descriptions from Pydantic models
field_definitions = get_nested_descriptions(RunConfig)
```

### Phase 3: Update Validation (2-3 hours)

#### Step 3.1: Update Strategy Validation
**File**: `src/trading_platform/strategy/yaml_strategy.py`

**Remove JSON schema validation, keep only:**
- Indicator registry validation (already exists)
- Predicate validation (already exists)

#### Step 3.2: Update RMM Validation
**Files**:
- `src/trading_platform/regime_market_manager/engine.py`
- `src/trading_platform/regime_market_manager/config.py`

**Remove JSON schema validation, rely on:**
- Feature validation
- Condition validation

### Phase 4: Testing (1 hour)

1. Run schema generator
2. Verify generated schemas match old ones
3. Run full test suite
4. Fix any breaking changes

### Phase 5: Cleanup (0.5 hours)

1. Delete old JSON schemas (they're now generated)
2. Add schema generation to CI/pre-commit
3. Update documentation

## Total Estimated Time: 6-9 hours

## Success Criteria

1. ✅ All JSON schemas generated from Pydantic models
2. ✅ Brief generation uses Pydantic descriptions
3. ✅ All validation uses Pydantic models (not JSON schemas)
4. ✅ Full test suite passes
5. ✅ No manual JSON schema maintenance needed
6. ✅ IDE autocomplete still works (via generated schemas)

## Dependencies

- RunConfig already has `extra="forbid"` ✅
- All RunConfig fields have descriptions ✅
- REM already has Pydantic models ✅

## Future Work (After This Migration)

- Migrate Strategy configs to Pydantic (11-16 hours)
- Migrate RMM configs to Pydantic (12-17 hours)
- Add nested config validation to RunConfig

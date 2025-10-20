# RMM Config Pydantic Migration Plan

## Status: Future Work (Not Yet Implemented)

This document outlines the plan for migrating RMM (Regime Market Manager) configurations to use Pydantic models with strict validation, similar to the REM config migration completed in Tasks 1-17.

## Background

RMM configurations are currently validated against `docs/schemas/rmm.schema.json` but don't enforce validation at runtime. According to the Phase 1 audit ([rmm_schema_audit.md](rmm_schema_audit.md)), the RMM schema has:
- **Grade: A-** (minor gaps)
- All 36 indicators implemented
- All 8 schema conditions implemented
- 3 items missing from schema but implemented:
  - `EMASlope` indicator
  - `cross_above` condition
  - `cross_below` condition

## Objectives

1. Create Pydantic models for RMM configs with `extra="forbid"`
2. Enforce strict validation to prevent typos and undefined indicators
3. Update schema to include missing implemented features
4. Maintain backward compatibility during migration
5. Achieve 100% test coverage for validation logic

## Proposed Approach

### Step 1: Update RMM Schema First

Before creating Pydantic models, update `docs/schemas/rmm.schema.json`:

**Add EMASlope to features enum (line 86):**
```json
"enum": [
  "SMA",
  "EMA",
  "EMASlope",  // ADD THIS
  "WMA",
  // ... rest
]
```

**Add cross conditions to predicate enum (line 183):**
```json
"enum": [
  "is_above",
  "is_below",
  "cross_above",     // ADD THIS
  "cross_below",     // ADD THIS
  "hour_is_in",
  // ... rest
]
```

### Step 2: Create Indicators Registry

Similar to REM, create `src/trading_platform/regime_market_manager/indicators_types.py`:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class IndicatorSpec:
    name: str
    description: str
    required_params: dict[str, type]
    optional_params: dict[str, tuple[type, Any]]  # (type, default)

# Share with Strategy registry or create RMM-specific subset?
RMM_INDICATORS_REGISTRY = {
    "sma": IndicatorSpec(...),
    "ema": IndicatorSpec(...),
    "ema_slope": IndicatorSpec(...),
    # ... all 37 indicators (36 + EMASlope)
}
```

**Decision Point**: Should RMM share `STRATEGY_INDICATORS_REGISTRY` or have its own?
- **Option A**: Share registry (DRY principle)
- **Option B**: Separate registry (RMM subset only)

**Recommendation**: Share registry if possible, use same indicator specs.

### Step 3: Design Pydantic Models with Discriminated Unions

Create `src/trading_platform/regime_market_manager/models.py`:

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

class SMAIndicator(BaseModel):
    model_config = {"extra": "forbid"}

    feature: Literal["sma"]
    length: int = Field(ge=1)
    source: str = "close"

class EMAIndicator(BaseModel):
    model_config = {"extra": "forbid"}

    feature: Literal["ema"]
    length: int = Field(ge=1)
    source: str = "close"

# Union of all indicator types
IndicatorFeature = SMAIndicator | EMAIndicator | ...

class RegimeCondition(BaseModel):
    """Regime classification condition."""
    model_config = {"extra": "forbid"}

    feature: str  # Must reference a defined feature
    condition: Literal[
        "is_above", "is_below", "cross_above", "cross_below",
        "hour_is_in", "hour_is_not_in", "day_of_week_is_in",
        "day_of_week_is_not_in", "percentile_is_above",
        "volatility_is_between"
    ]
    compare_to: str | float  # Feature name or numeric value

class RegimeDefinition(BaseModel):
    """Single regime definition."""
    model_config = {"extra": "forbid"}

    name: str
    conditions: list[RegimeCondition]

class RMMConfig(BaseModel):
    """Complete RMM configuration."""
    model_config = {"extra": "forbid"}

    name: str | None = None
    version: str | None = None
    features: list[IndicatorFeature] = Field(default_factory=list)
    regimes: list[RegimeDefinition]
    default_regime: str | None = None

    @field_validator("default_regime")
    def validate_default_regime(cls, v, info):
        """Ensure default_regime is one of the defined regimes."""
        if v is not None:
            regime_names = [r.name for r in info.data.get("regimes", [])]
            if v not in regime_names:
                raise ValueError(
                    f"default_regime '{v}' not found in regimes: {regime_names}"
                )
        return v
```

### Step 4: Handle Cross-Reference Validation

RMM configs reference features by name in conditions. Use Pydantic validators:

```python
@field_validator("conditions")
def validate_feature_references(cls, v, info):
    """Ensure all feature references exist."""
    feature_names = [f.name for f in info.data.get("features", [])]
    for cond in v:
        if isinstance(cond.compare_to, str) and cond.compare_to not in feature_names:
            raise ValueError(
                f"Condition references undefined feature: {cond.compare_to}"
            )
        if cond.feature not in feature_names:
            raise ValueError(
                f"Condition references undefined feature: {cond.feature}"
            )
    return v
```

### Step 5: Backward Compatibility Strategy

Similar to REM migration:
1. Accept both validated models and raw dicts in `RegimeMarketManager.__init__()`
2. Check for "version" field to determine format
3. Legacy configs bypass validation
4. New configs enforce strict validation

```python
class RegimeMarketManager:
    def __init__(self, config: dict | RMMConfig):
        if isinstance(config, RMMConfig):
            # Already validated
            self.config = config
        elif self._is_legacy_format(config):
            # Legacy - bypass validation
            self.config = config
        else:
            # New format - validate
            self.config = RMMConfig(**config)

    @staticmethod
    def _is_legacy_format(config: dict) -> bool:
        """Check if config lacks version field."""
        return "version" not in config
```

### Step 6: Update Call Sites

Files to update:
- `src/trading_platform/regime_market_manager/engine.py` - Main entry point
- `src/trading_platform/backtester/orchestrator.py` - RMM loading
- All test fixtures using RMM configs

### Step 7: Migration of Golden RMM Configs

Update golden RMM YAML files (if any exist):
- Add version fields
- Ensure all features have explicit type fields

## Challenges

### Challenge 1: Shared Indicator Registry

RMM and Strategy share the same indicators. Should they share the same registry?

**Solution**:
- **Option A**: Share registry - requires coordinating types between modules
- **Option B**: Separate registries - easier isolation but code duplication

**Recommendation**: Start with separate registry for simplicity, consolidate later if needed.

### Challenge 2: Cross-Reference Validation

Conditions reference features by name. Need to validate these references.

**Solution**: Use Pydantic `field_validator` to check that all referenced features exist.

### Challenge 3: Default Regime Validation

`default_regime` must be one of the defined regime names.

**Solution**: Use Pydantic `field_validator` to check against regime list.

### Challenge 4: Time-Based Conditions

Conditions like `hour_is_in` and `day_of_week_is_in` have list values.

**Solution**: Create specialized condition models with proper validation:
```python
class HourIsInCondition(BaseModel):
    condition: Literal["hour_is_in"]
    hours: list[int] = Field(..., min_length=1)

    @field_validator("hours")
    def validate_hours(cls, v):
        for hour in v:
            if not 0 <= hour <= 23:
                raise ValueError(f"Hour must be 0-23, got {hour}")
        return v
```

## Estimated Effort

- Schema updates: 0.5 hours (add 3 missing items)
- Indicators Registry: 2-3 hours (37 indicators, may share with Strategy)
- Pydantic Models: 5-7 hours (complex validation, multiple condition types)
- Call Site Updates: 2-3 hours
- Testing: 3-4 hours
- **Total: 12-17 hours**

## Dependencies

- Completion of REM migration (Tasks 1-17) ✅
- RMM schema audit (Task 2) ✅
- Strategy schema audit (Task 1) ✅ (for shared indicators)
- Understanding of current RMM validation logic

## Success Criteria

1. All 37 indicators have spec entries in registry (36 original + EMASlope)
2. All 10 conditions supported (8 schema + cross_above/cross_below)
3. Schema updated to include all implemented features
4. Pydantic models cover all schema cases
5. `extra="forbid"` catches typos and unknown indicators/conditions
6. Cross-reference validation works (feature names in conditions)
7. Default regime validation works
8. 100% test coverage for validation logic
9. All existing tests pass without modification
10. Clear error messages for validation failures

## References

- RMM Schema: [docs/schemas/rmm.schema.json](../schemas/rmm.schema.json)
- RMM Audit: [rmm_schema_audit.md](rmm_schema_audit.md)
- REM Migration Example: [docs/migration_guides/rem_config_v2.md](../migration_guides/rem_config_v2.md)
- Current Implementation: [src/trading_platform/regime_market_manager/engine.py](../../src/trading_platform/regime_market_manager/engine.py)
- Indicators Registry: [src/trading_platform/strategy/indicators_registry.py](../../src/trading_platform/strategy/indicators_registry.py)

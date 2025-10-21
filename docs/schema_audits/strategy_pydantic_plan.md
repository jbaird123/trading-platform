# Strategy Config Pydantic Migration Plan

## Status: Completed (StrategyConfig Pydantic validation in place)

Strategy configurations are now validated via the `StrategyConfig` Pydantic model in `src/trading_platform/strategy/models.py`, with indicator types enforced directly against the unified registry. The details below are retained for historical context.

## Background

Prior to the migration, strategy configurations were validated against `docs/schemas/strategy.schema.json`. That legacy schema has been retired in favour of runtime validation through `StrategyConfig`. According to the Phase 1 audit ([strategy_schema_audit.md](strategy_schema_audit.md)), the schema previously had:
- **Grade: A+** (perfect alignment)
- All 37 indicators implemented
- All 6 conditions implemented
- No gaps found

## Objectives

1. Create Pydantic models for Strategy configs with `extra="forbid"`
2. Enforce strict validation to prevent typos and undefined indicators
3. Maintain backward compatibility during migration
4. Achieve 100% test coverage for validation logic

## Proposed Approach

### Step 1: Create Indicators Registry (Similar to REM)

Create `src/trading_platform/strategy/indicators_types.py`:
```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class IndicatorSpec:
    name: str
    description: str
    required_params: dict[str, type]
    optional_params: dict[str, tuple[type, Any]]  # (type, default)

STRATEGY_INDICATORS_REGISTRY = {
    "sma": IndicatorSpec(...),
    "ema": IndicatorSpec(...),
    "rsi": IndicatorSpec(...),
    # ... all 37 indicators
}
```

### Step 2: Design Pydantic Models with Discriminated Unions

Create `src/trading_platform/strategy/models.py`:
```python
from pydantic import BaseModel, Field

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

class StrategyConfig(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    version: str | None = None
    features: list[IndicatorFeature] = Field(..., discriminator="feature")
    entry_conditions: dict  # To be designed
    exit_conditions: dict  # To be designed
```

### Step 3: Handle Predicate Validation

Strategy predicates (is_above, is_below, cross_above, etc.) need special handling:
- Create PredicateCondition model
- Validate left/right operands are valid feature names
- Ensure predicates are in allowed list (6 total)

### Step 4: Backward Compatibility Strategy

Similar to REM migration:
1. Accept both validated models and raw dicts in `compile_strategy()`
2. Check for "version" field or feature "type" fields to determine format
3. Legacy configs bypass validation
4. New configs enforce strict validation

### Step 5: Update Call Sites

Files to update:
- `src/trading_platform/strategy/yaml_strategy.py` - Main entry point
- `src/trading_platform/backtester/orchestrator.py` - Strategy loading
- `src/trading_platform/cli.py` - CLI strategy loading
- All test fixtures using Strategy configs

### Step 6: Migration of Golden Strategies

Update golden strategy YAML files:
- `configs/golden_strategies/ema_crossover/*/strategy.yaml`
- Add version fields
- Ensure all features have explicit type fields if needed

## Challenges

### Challenge 1: Feature References

Strategy configs reference features by name in conditions:
```yaml
entry_conditions:
  - feature: "fast_ema"
    condition: "cross_above"
    compare_to: "slow_ema"
```

Pydantic needs to validate that "fast_ema" and "slow_ema" are defined features.

**Solution**: Use Pydantic root_validator to check cross-references.

### Challenge 2: Dynamic Feature Count

Strategies can have arbitrary number of features (0-N).

**Solution**: Use `list[IndicatorFeature]` with discriminated union.

### Challenge 3: Parameters vs Features

Strategy has both "parameters" (tunable) and "features" (computed indicators).

**Solution**: Separate Pydantic models for each, validate independently.

## Estimated Effort

- Indicators Registry: 2-3 hours (37 indicators)
- Pydantic Models: 4-6 hours (complex validation)
- Call Site Updates: 2-3 hours
- Testing: 3-4 hours
- **Total: 11-16 hours**

## Dependencies

- Completion of REM migration (Tasks 1-17) ✅
- Strategy schema audit (Task 1) ✅
- Understanding of current validation logic

## Success Criteria

1. All 37 indicators have spec entries in registry
2. Pydantic models cover all schema cases
3. `extra="forbid"` catches typos and unknown indicators
4. 100% test coverage for validation logic
5. All existing tests pass without modification
6. Clear error messages for validation failures

## References

- StrategyConfig Pydantic model: [src/trading_platform/strategy/models.py](../../src/trading_platform/strategy/models.py)
- Strategy Audit: [strategy_schema_audit.md](strategy_schema_audit.md)
- REM Migration Example: [docs/migration_guides/rem_config_v2.md](../migration_guides/rem_config_v2.md)
- Current Implementation: [src/trading_platform/strategy/yaml_strategy.py](../../src/trading_platform/strategy/yaml_strategy.py)

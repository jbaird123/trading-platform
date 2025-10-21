# RunConfig Pydantic Migration Plan

## Status: Future Work (Not Yet Implemented)

This document outlines the plan for enhancing RunConfig with stricter Pydantic validation using `extra="forbid"`, similar to the REM config migration completed in Tasks 1-17.

## Background

RunConfig is **already using Pydantic** (see [src/trading_platform/core/config.py](../../src/trading_platform/core/config.py)), but lacks strict validation. According to the Phase 1 audit ([run_config_schema_audit.md](run_config_schema_audit.md)):
- **Grade: C+** (schema exists but not enforced)
- RunConfig is a Pydantic BaseModel
- Schema file exists but is minimal
- **Missing**: `extra="forbid"` on models
- **Missing**: Nested config validation (strategy, rem, rmm as dicts)

## Current State

### What's Already Good
```python
class RunConfig(BaseModel):
    """Already using Pydantic."""
    user_id: str = Field("default_user", ...)
    run_id: str = Field(default_factory=gen_run_id, ...)
    run_seed: int = Field(42, ...)
    # ... many more fields

    @model_validator(mode="after")
    def validate_instrument_symbol(self) -> RunConfig:
        """Already has custom validation."""
        # ...
```

### What Needs Improvement
1. **No `extra="forbid"`** - Unknown fields are silently ignored
2. **Nested configs as dicts** - `strategy`, `rem_config`, `rmm_config` are raw dicts
3. **Schema is minimal** - Only covers basic fields, not comprehensive

## Objectives

1. Add `extra="forbid"` to RunConfig and all nested models
2. Optionally validate nested configs (strategy, rem, rmm) using their Pydantic models
3. Update schema to be comprehensive
4. Maintain backward compatibility
5. Ensure 100% test coverage

## Proposed Approach

### Step 1: Add `extra="forbid"` to Existing Models

Update `src/trading_platform/core/config.py`:

```python
class FeatureConfig(BaseModel):
    """Configuration for a single technical indicator/feature."""
    model_config = {"extra": "forbid"}  # ADD THIS

    name: str = Field(...)
    type: str = Field(...)
    # ... rest

class RunConfig(BaseModel):
    """Run configuration with strict validation."""
    model_config = {"extra": "forbid"}  # ADD THIS

    user_id: str = Field(...)
    # ... rest
```

**Impact**: This will catch typos in run config YAML files.

**Risk**: May break existing configs that have extra fields. Need migration period.

### Step 2: Decide on Nested Config Validation

RunConfig currently has these nested config fields as raw dicts:
- `strategy: dict[str, Any]` - Strategy definition
- `rem_config: dict[str, Any]` - REM configuration
- `rmm_config: dict[str, Any]` - RMM configuration

**Option A: Keep as dicts (recommended for Phase 1)**
```python
# Current approach - no change
strategy: dict[str, Any] = Field(default_factory=dict, ...)
rem_config: dict[str, Any] | None = Field(default=None, ...)
rmm_config: dict[str, Any] | None = Field(default=None, ...)
```

**Pros**:
- Simpler migration
- Nested configs validated by their own systems
- RunConfig doesn't need to know about nested config schemas

**Cons**:
- No validation at RunConfig level
- Errors only caught later when loading nested configs

**Option B: Validate nested configs (future enhancement)**
```python
from trading_platform.strategy.models import StrategyConfig
from trading_platform.risk_manager import REMConfig
from trading_platform.regime_market_manager.models import RMMConfig

strategy: StrategyConfig | dict[str, Any] = Field(...)
rem_config: REMConfig | dict[str, Any] | None = Field(default=None, ...)
rmm_config: RMMConfig | dict[str, Any] | None = Field(default=None, ...)
```

**Pros**:
- Full validation at load time
- Catch config errors early

**Cons**:
- Tight coupling between modules
- Circular dependency risk
- More complex migration

**Recommendation**: Start with Option A, consider Option B after Strategy/RMM Pydantic migrations are complete.

### Step 3: Update Schema File

The standalone JSON schema has been retired; `RunConfig` validation now relies directly on the Pydantic model (`src/trading_platform/core/config.py`). Historical notes about expanding `docs/schemas/run_config.schema.json` are kept here for completeness, but no further action is required.

### Step 4: Backward Compatibility Strategy

Unlike REM (which had old/new formats), RunConfig migration is simpler:

1. **Add `extra="forbid"`** to catch new errors
2. **Test existing configs** to ensure no extra fields
3. **Fix any broken configs** that have extra fields
4. **Document breaking change** in migration guide

**Migration Period**: None needed - this is a one-time update since RunConfig files are internal (not user-facing like Strategy/REM configs).

### Step 5: Testing Strategy

1. **Unit tests**: Test that `extra="forbid"` catches unknown fields
2. **Integration tests**: Ensure all golden configs still load
3. **Regression tests**: Run full test suite to catch any breakage

**Test Example**:
```python
def test_run_config_forbids_extra_fields():
    """Test that RunConfig rejects unknown fields."""
    config_dict = {
        "user_id": "test",
        "unknown_field": "should fail",  # Extra field
        "instrument": {"symbol": "EURUSD"},
        # ... required fields
    }

    with pytest.raises(ValidationError) as exc_info:
        RunConfig(**config_dict)

    assert "extra_forbidden" in str(exc_info.value)
```

### Step 6: Update Call Sites

RunConfig is already instantiated via Pydantic in most places. Main areas to check:
- `src/trading_platform/cli.py` - CLI loading
- `src/trading_platform/backtester/orchestrator.py` - Backtest runs
- Test fixtures creating RunConfig instances

**Expected**: Minimal changes needed since Pydantic is already in use.

## Challenges

### Challenge 1: Nested Configs as Dicts

RunConfig contains strategy/rem/rmm as raw dicts. Should we validate them?

**Solution**: Phase 1 - keep as dicts. Phase 2 (after Strategy/RMM migrations) - add typed validation.

### Challenge 2: Schema Drift

JSON schema may drift from Pydantic model over time.

**Solution**:
- Option A: Generate schema from Pydantic using `model_json_schema()`
- Option B: Add CI test to verify schema matches Pydantic model
- **Recommendation**: Option A for consistency

### Challenge 3: Breaking Existing Configs

Adding `extra="forbid"` may break configs with typos or extra fields.

**Solution**:
1. Audit all existing run configs
2. Fix any that have extra fields
3. Add validation to CI to prevent regression

### Challenge 4: Path Fields

RunConfig has `runs_dir: Path` field, which may not serialize well to JSON.

**Solution**: Already handled by Pydantic's Path serialization. No change needed.

## Estimated Effort

- Add `extra="forbid"` to models: 0.5 hours
- Update schema (generate from Pydantic): 1-2 hours
- Audit existing run configs: 1 hour
- Fix broken configs (if any): 1-2 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- **Total: 6-9 hours**

**Note**: Much simpler than REM/Strategy/RMM migrations because Pydantic is already in use.

## Dependencies

- Completion of REM migration (Tasks 1-17) ✅
- RunConfig schema audit (Task 3) ✅
- Understanding of current RunConfig usage

## Success Criteria

1. `extra="forbid"` enabled on RunConfig and FeatureConfig
2. All existing tests pass without modification
3. Schema matches Pydantic model exactly
4. Clear error messages for validation failures
5. Documentation updated with examples
6. 100% test coverage for validation logic

## Non-Goals

The following are **out of scope** for this migration:

1. **Nested config validation** (strategy/rem/rmm) - Defer until their Pydantic migrations complete
2. **New RunConfig fields** - Only add validation, don't change functionality
3. **Breaking schema changes** - Maintain backward compatibility where possible

## References

- RunConfig Implementation: [src/trading_platform/core/config.py](../../src/trading_platform/core/config.py)
- RunConfig Pydantic model: [src/trading_platform/core/config.py](../../src/trading_platform/core/config.py)
- RunConfig Audit: [run_config_schema_audit.md](run_config_schema_audit.md)
- REM Migration Example: [docs/migration_guides/rem_config_v2.md](../migration_guides/rem_config_v2.md)

## Migration Example

Since RunConfig is internal (not user-facing), migration is simpler than REM:

### Before (Current)
```python
class RunConfig(BaseModel):
    # No extra="forbid"
    user_id: str = Field("default_user", ...)
    run_id: str = Field(default_factory=gen_run_id, ...)
    # ... rest
```

### After (Enhanced)
```python
class RunConfig(BaseModel):
    model_config = {"extra": "forbid"}  # ADD THIS

    user_id: str = Field("default_user", ...)
    run_id: str = Field(default_factory=gen_run_id, ...)
    # ... rest (no other changes needed)
```

### Error Example

**Old behavior** (extra field silently ignored):
```python
config = RunConfig(
    user_id="test",
    typo_field="oops",  # Silently ignored
    instrument={"symbol": "EURUSD"},
    # ...
)
# No error - typo_field ignored
```

**New behavior** (extra field rejected):
```python
config = RunConfig(
    user_id="test",
    typo_field="oops",  # Now caught!
    instrument={"symbol": "EURUSD"},
    # ...
)
# ValidationError: Extra inputs are not permitted
```

## Implementation Phases

### Phase 1: Basic Validation (This Migration)
- Add `extra="forbid"` to RunConfig and FeatureConfig
- Update schema to match Pydantic model
- Fix any broken configs
- **Effort**: 6-9 hours

### Phase 2: Nested Config Validation (Future)
- Add typed validation for strategy/rem/rmm configs
- Requires Strategy and RMM Pydantic migrations to complete first
- **Effort**: TBD (depends on Strategy/RMM migration complexity)

## Testing Checklist

- [ ] Add test for `extra="forbid"` on RunConfig
- [ ] Add test for `extra="forbid"` on FeatureConfig
- [ ] Verify all golden configs still load
- [ ] Run full test suite (all 1569 tests pass)
- [ ] Test error messages are clear and helpful
- [ ] Test that valid configs still work
- [ ] Test that schema validation matches Pydantic validation

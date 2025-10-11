# Unified Indicator Registry Refactoring Plan

**Status:** In Progress
**Priority:** HIGH - Core architectural improvement
**Estimated Time:** 4-6 hours

## Problem Statement

Currently, the indicator system has **three disconnected sources of truth**:

1. **indicators_registry.py** - Metadata (36 indicators) - NOT used at
   runtime
2. **indicator_safety.py** - Safety classifications (29 indicators) -
   NOT used at runtime
3. **features.py** - Hardcoded if/elif branches (~35 indicators) -
   **ACTUALLY RUNS**

This creates:
- ❌ Can add indicators without registry entries
- ❌ Registries can drift out of sync
- ❌ No single source of truth
- ❌ Difficult to maintain and extend

## Solution: Single Unified Registry

Merge everything into **one registry** that:
- ✅ Contains all metadata (display, params, category, description)
- ✅ Contains safety classification
- ✅ Contains implementation function
- ✅ Is used by features.py at runtime
- ✅ Cannot add indicators without complete metadata

## Phase 1: Make Registry Control Execution

### Step 1.1: Add Implementation Functions to Registry

Update `indicators_registry.py` to include function references:

```python
from trading_platform.strategy import feature_implementations as impl

INDICATORS = {
    "EMA": {
        "display": "Exponential Moving Average",
        "category": "trend",
        "description": "Exponentially weighted average of prices.",
        "params": [{"name": "length", "type": "int", "default": 14}],
        "safety": "validated",
        "implementation": impl.compute_ema,  # ← NEW: function reference
        "output_type": "single",  # single, multi, dataframe
    },
}
```

**Files to modify:**
- `src/trading_platform/strategy/indicators_registry.py`
- Create `src/trading_platform/strategy/feature_implementations.py`
  (extract functions from features.py)

### Step 1.2: Refactor features.py to Use Registry

Replace hardcoded if/elif with registry lookup:

**Before:**
```python
def compute_features(df, specs, strategy_parameters):
    for spec in specs:
        typ = spec['type']
        if typ == "EMA":
            # hardcoded logic
        elif typ == "RSI":
            # hardcoded logic
        # ... 35 more branches
```

**After:**
```python
def compute_features(df, specs, strategy_parameters):
    for spec in specs:
        typ = spec['type']

        # Get indicator from registry
        indicator = INDICATORS.get(typ)
        if not indicator:
            raise ValueError(
                f"Unknown indicator '{typ}'. "
                f"Not in registry. Available: {list(INDICATORS.keys())}"
            )

        # Call implementation from registry
        impl_fn = indicator['implementation']
        params = resolve_params(spec['params'], strategy_parameters)
        result = impl_fn(df, params)

        # Handle output based on type
        if indicator['output_type'] == 'single':
            out[name] = result
        elif indicator['output_type'] == 'multi':
            # Handle multiple columns (BB, MACD, etc.)
            for col_name, col_data in result.items():
                out[f"{name}_{col_name}"] = col_data
```

**Files to modify:**
- `src/trading_platform/strategy/features.py`

### Step 1.3: Test Phase 1

Ensure all existing tests pass:
- `pytest tests/strategy/test_features.py -v`
- `pytest tests/integration/ -v`
- `pytest tests/validation/ -v`

**Success Criteria:**
- ✅ All tests pass
- ✅ features.py has no hardcoded if/elif for indicators
- ✅ Adding new indicator requires registry entry
- ✅ Attempting to use unregistered indicator raises clear error

---

## Phase 2: Merge Safety Registry

### Step 2.1: Add Safety Data to Main Registry

Move safety classifications from `indicator_safety.py` into
`indicators_registry.py`:

```python
INDICATORS = {
    "EMA": {
        # ... existing fields ...
        "safety": "validated",  # ← Already there from Phase 1
    },
}
```

Already done! The registry already has the safety field.

### Step 2.2: Create Safety Helper Functions

Add helper functions to `indicators_registry.py`:

```python
from enum import Enum

class SafetyLevel(Enum):
    SAFE = "safe"
    VALIDATED = "validated"
    REQUIRES_TEST = "requires_test"
    ALLOW_LOOKAHEAD = "allow_lookahead"

def get_safety_level(indicator_type: str) -> SafetyLevel:
    """Get safety level for an indicator from registry."""
    indicator = INDICATORS.get(indicator_type)
    if not indicator:
        return SafetyLevel.REQUIRES_TEST
    return SafetyLevel(indicator["safety"])

def is_indicator_safe(indicator_type: str) -> bool:
    """Check if indicator is safe to use."""
    level = get_safety_level(indicator_type)
    return level in (SafetyLevel.SAFE, SafetyLevel.VALIDATED)

# ... other helper functions from indicator_safety.py
```

### Step 2.3: Update All Imports

Find and replace all imports:

**Before:**
```python
from trading_platform.strategy.indicator_safety import (
    get_safety_level,
    SafetyLevel,
)
```

**After:**
```python
from trading_platform.strategy.indicators_registry import (
    get_safety_level,
    SafetyLevel,
)
```

**Files to update:**
- `tests/strategy/test_indicator_safety.py`
- `tests/strategy/test_indicator_bias_detection.py`
- Any other files importing from indicator_safety

### Step 2.4: Delete indicator_safety.py

```bash
rm src/trading_platform/strategy/indicator_safety.py
```

### Step 2.5: Update Tests

Ensure all safety-related tests pass:
- `pytest tests/strategy/test_indicator_safety.py -v`
- `pytest tests/strategy/test_indicator_bias_detection.py -v`

**Success Criteria:**
- ✅ All tests pass
- ✅ indicator_safety.py deleted
- ✅ All safety functions work from unified registry
- ✅ No import errors

---

## Implementation Order

1. **Create feature_implementations.py** - Extract implementation
   functions
2. **Update indicators_registry.py** - Add implementation references
3. **Refactor features.py** - Use registry instead of if/elif
4. **Test Phase 1** - Verify all tests pass
5. **Move safety helpers to registry** - Add SafetyLevel enum and
   functions
6. **Update all imports** - Point to unified registry
7. **Delete indicator_safety.py**
8. **Test Phase 2** - Verify all tests pass
9. **Update documentation** - Reflect new architecture

---

## Benefits After Completion

1. **Single Source of Truth**
   - One registry controls everything
   - Cannot get out of sync

2. **Enforced Completeness**
   - Can't add indicator without metadata
   - Can't use indicator not in registry

3. **Easier Maintenance**
   - One place to add new indicators
   - Clear structure for contributions

4. **Better Tooling**
   - UI generators can use registry
   - Documentation can auto-generate from registry
   - IDE can provide better autocomplete

5. **Safety Enforcement**
   - Safety checks integrated with usage
   - Clear classification for all indicators

---

## Risk Mitigation

1. **Comprehensive Testing**
   - Run full test suite after each phase
   - Don't proceed if tests fail

2. **Incremental Changes**
   - Phase 1 and Phase 2 are independently testable
   - Can roll back to previous phase if issues

3. **No Behavior Changes**
   - Pure refactoring - same outputs
   - All existing functionality preserved

---

## Estimated Timeline

- **Phase 1:** 2-3 hours
  - Extract implementations: 1 hour
  - Refactor features.py: 1 hour
  - Testing: 30 min

- **Phase 2:** 1-2 hours
  - Move safety functions: 30 min
  - Update imports: 30 min
  - Testing: 30 min

- **Documentation:** 30 min

**Total: 4-6 hours**

---

## Success Metrics

After completion:
- ✅ `features.py` has no hardcoded if/elif branches for indicators
- ✅ All 36 indicators in single unified registry
- ✅ All tests passing (100% coverage maintained)
- ✅ `indicator_safety.py` deleted
- ✅ Clear error when attempting to use unregistered indicator
- ✅ Documentation updated

---

## Future Enhancements (Post-Refactor)

Once unified registry is in place:
1. Auto-generate JSON schema from registry
2. Build indicator UI selector from registry
3. Auto-generate documentation
4. Add indicator versioning
5. Add indicator deprecation support

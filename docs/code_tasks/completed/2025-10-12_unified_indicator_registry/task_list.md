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

### Step 1.0: Design Standard Implementation Interface

**Critical Decision: Standardize ALL indicator function signatures**

Every indicator implementation will follow this exact interface:

```python
def compute_indicator_name(
    df: pd.DataFrame,
    params: dict[str, Any],
    source: str = "close",
    source_ref: str | None = None,
) -> pd.Series | dict[str, pd.Series]:
    """
    Standard indicator implementation interface.

    Args:
        df: OHLCV DataFrame with columns: open, high, low, close, volume
        params: Resolved parameters dict (already substituted ${vars})
        source: Price source (open/high/low/close/hl2/ohlc4)
        source_ref: Optional reference to another column in df

    Returns:
        - Single pd.Series for single-output indicators (EMA, RSI, ATR)
        - Dict[str, pd.Series] for multi-output indicators (BB, MACD, ADX)
          Keys are column suffixes: {"upper": series, "lower": series}
    """
    pass
```

**Why standardize?**
- ✅ Uniform calling convention in compute_features()
- ✅ No branching logic needed
- ✅ Easy to add new indicators
- ✅ No metadata about function signatures required
- ✅ Future-proof and maintainable

**Examples by indicator type:**

```python
# Single-output indicator
def compute_ema(df, params, source="close", source_ref=None):
    series = _price_series(df, source)
    return ema(series, params['length'])

# Multi-output indicator (returns dict)
def compute_bb(df, params, source="close", source_ref=None):
    bb = ta.bbands(
        close=_price_series(df, source),
        length=params['length'],
        std=params['ndev']
    )
    return {
        "upper": bb.iloc[:, 2],
        "lower": bb.iloc[:, 0],
        "middle": bb.iloc[:, 1],
    }

# Indicator with source_ref support (HHV, LLV)
def compute_hhv(df, params, source="high", source_ref=None):
    if source_ref:
        series = pd.Series(df[source_ref], dtype="float64")
    else:
        series = _price_series(df, source)
    return hhv(series, params['length'])

# Indicator that needs full DataFrame (ATR, ADX)
def compute_atr(df, params, source="close", source_ref=None):
    # source parameter unused but signature is consistent
    return atr(df, params['length'])

# Multi-column DataFrame output (ADX)
def compute_adx(df, params, source="close", source_ref=None):
    adx_df = adx(df, params['length'])
    return {
        "ADX": adx_df["ADX"],
        "DI+": adx_df["DI+"],
        "DI-": adx_df["DI-"],
    }
```

**Implementation Strategy:**
1. Create feature_implementations.py with standard interface
2. Extract each indicator into compute_X() function
3. Wrap existing helper functions (ema, rsi, atr, etc.) - keep those as-is
4. Handle parameter extraction inside each compute_X() function
5. Return Series or dict based on output type

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

**Before (615 lines, ~35 if/elif branches):**
```python
def compute_features(df, specs, strategy_parameters):
    for spec in specs:
        typ = spec['type']
        name = spec['name']
        params = spec.get('params', {})
        source = spec.get('source', 'close')

        # Resolve parameter substitutions
        resolved_params = {
            k: _resolve_parameter(v, strategy_parameters)
            for k, v in params.items()
        }

        if typ == "EMA":
            length = int(resolved_params.get("length", 14))
            out[name] = ema(_price_series(df, source), length)
        elif typ == "RSI":
            length = int(resolved_params.get("length", 14))
            out[name] = rsi(_price_series(df, source), length)
        elif typ == "BB":
            length = int(resolved_params.get("length", 20))
            ndev = float(resolved_params.get("ndev", 2.0))
            bb = ta.bbands(close=_price_series(df, source), ...)
            out[f"{name}_upper"] = bb.iloc[:, 2]
            out[f"{name}_lower"] = bb.iloc[:, 0]
            out[f"{name}_middle"] = bb.iloc[:, 1]
        # ... 32 more branches
```

**After (clean, simple loop):**
```python
def compute_features(df, specs, strategy_parameters=None):
    if strategy_parameters is None:
        strategy_parameters = {}

    out = df.copy()

    for spec in specs or []:
        name = str(spec.get("name"))
        typ = str(spec.get("type"))
        params = spec.get("params") or {}
        source = str(spec.get("source", "close"))
        timeframe = spec.get("timeframe")
        source_ref = None

        # Extract source_ref if present
        _src_ref_val = spec.get("source_ref")
        if isinstance(_src_ref_val, dict) and ("ref" in _src_ref_val):
            ref_val = _src_ref_val.get("ref")
            source_ref = str(ref_val) if ref_val is not None else None

        if not name:
            continue

        # Handle higher-timeframe features (preserved from original)
        if timeframe:
            df_resampled = _resample_to_higher_timeframe(df, timeframe)
            temp_spec = {
                "name": name,
                "type": typ,
                "params": params,
                "source": source,
            }
            if source_ref:
                temp_spec["source_ref"] = {"ref": source_ref}
            df_htf = compute_features(
                df_resampled, [temp_spec], strategy_parameters
            )
            htf_series = df_htf[name].reindex(df.index, method="ffill")
            out[name] = htf_series
            continue

        # Resolve parameter substitutions (${param_name})
        resolved_params = {
            k: _resolve_parameter(v, strategy_parameters)
            for k, v in params.items()
        }

        # Get indicator from registry
        indicator = INDICATORS.get(typ)
        if not indicator:
            raise ValueError(
                f"Unknown indicator '{typ}'. Not in registry. "
                f"Available: {sorted(INDICATORS.keys())}"
            )

        # Call implementation with standard interface
        impl_fn = indicator['implementation']
        result = impl_fn(df, resolved_params, source, source_ref)

        # Handle output based on return type
        if isinstance(result, dict):
            # Multi-column output (BB, MACD, ADX, etc.)
            for col_name, col_data in result.items():
                out[f"{name}_{col_name}"] = col_data
        else:
            # Single-column output (EMA, RSI, ATR, etc.)
            out[name] = result

    return out
```

**Key improvements:**
- ✅ No more if/elif branches for indicators
- ✅ Uniform calling: `impl_fn(df, params, source, source_ref)`
- ✅ Output type determined by return value (Series vs dict)
- ✅ Clear error for unregistered indicators
- ✅ Preserves timeframe handling
- ✅ Preserves parameter substitution
- ✅ ~200 lines shorter

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
   - Start with 5-10 simple indicators (EMA, RSI, SMA, WMA, ATR)
   - Use standard interface: `compute_X(df, params, source, source_ref)`
   - Test each function independently

2. **Update indicators_registry.py** - Add implementation references
   - Add `"implementation": impl.compute_X` for each indicator
   - No need for `output_type` metadata (return type tells us)

3. **Refactor features.py** - Use registry instead of if/elif
   - Keep helper functions (_price_series, _resolve_parameter, etc.)
   - Replace if/elif loop with registry lookup
   - Handle dict vs Series returns
   - Preserve timeframe handling

4. **Migrate remaining indicators incrementally**
   - Do 5-10 at a time, test after each batch
   - Complex indicators last (ICHIMOKU, SUPERTREND, candlesticks)

5. **Test Phase 1** - Verify all tests pass

6. **Move safety helpers to registry** - Add SafetyLevel enum and
   functions

7. **Update all imports** - Point to unified registry

8. **Delete indicator_safety.py**

9. **Test Phase 2** - Verify all tests pass

10. **Update documentation** - Reflect new architecture

## Migration Checklist by Indicator Type

### Batch 1: Simple Single-Output (Start Here)
- [ ] EMA - `compute_ema(df, params, source, source_ref) -> Series`
- [ ] SMA - `compute_sma(df, params, source, source_ref) -> Series`
- [ ] WMA - `compute_wma(df, params, source, source_ref) -> Series`
- [ ] RSI - `compute_rsi(df, params, source, source_ref) -> Series`
- [ ] ATR - `compute_atr(df, params, source, source_ref) -> Series`
- [ ] ROC - `compute_roc(df, params, source, source_ref) -> Series`

### Batch 2: Rolling Window Indicators
- [ ] HHV - `compute_hhv(df, params, source, source_ref) -> Series`
- [ ] LLV - `compute_llv(df, params, source, source_ref) -> Series`
- [ ] EMASlope - `compute_ema_slope(df, params, source, source_ref) -> Series`
- [ ] BBWidth - `compute_bb_width(df, params, source, source_ref) -> Series`

### Batch 3: Multi-Output Indicators
- [ ] BB - `compute_bb(df, params, source, source_ref) -> dict`
  - Returns: `{"upper": Series, "lower": Series, "middle": Series}`
- [ ] MACD - `compute_macd(df, params, source, source_ref) -> dict`
  - Returns: `{"macd": Series, "signal": Series, "diff": Series}`
- [ ] DC - `compute_dc(df, params, source, source_ref) -> dict`
  - Returns: `{"upper": Series, "lower": Series}`

### Batch 4: Complex Indicators
- [ ] ADX - `compute_adx(df, params, source, source_ref) -> dict`
- [ ] PSAR - `compute_psar(df, params, source, source_ref) -> dict`
- [ ] STOCH - `compute_stoch(df, params, source, source_ref) -> dict`
- [ ] KC - `compute_kc(df, params, source, source_ref) -> dict`

### Batch 5: Volume/Advanced
- [ ] OBV - `compute_obv(df, params, source, source_ref) -> Series`
- [ ] CMF - `compute_cmf(df, params, source, source_ref) -> Series`
- [ ] VWAP - `compute_vwap(df, params, source, source_ref) -> Series`
- [ ] CHOP - `compute_chop(df, params, source, source_ref) -> Series`

### Batch 6: Very Complex
- [ ] ICHIMOKU - `compute_ichimoku(df, params, source, source_ref) -> dict`
- [ ] SUPERTREND - `compute_supertrend(df, params, source, source_ref) -> dict`
- [ ] SWING_HIGH/LOW - `compute_swing_points(df, params, ...) -> dict`

### Batch 7: Candlestick Patterns (6 total)
- [ ] CDL_DOJI, CDL_HAMMER, CDL_ENGULFING, CDL_MORNINGSTAR,
      CDL_EVENINGSTAR, CDL_HARAMI

### Batch 8: Custom/RMM
- [ ] ATRPercentile
- [ ] RealizedVolatility
- [ ] VolumeZScore
- [ ] FIB

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

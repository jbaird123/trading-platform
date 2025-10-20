# RMM Schema Audit

**Date:** 2025-10-19
**Schema File:** `docs/schemas/rmm.schema.json`
**Implementation Files:**
- `src/trading_platform/regime_market_manager/engine.py`
- `src/trading_platform/strategy/indicators_registry.py` (shared)

---

## Schema vs Registry: Indicator Types

### Indicators in RMM Schema (Lines 83-120)
RMM schema references 36 indicator types (same as strategy schema minus EMASlope):

```
SMA, EMA, WMA, MACD, PSAR, ADX, RSI, STOCH, CCI, ROC, BB, BBWidth,
ATR, ATRPercentile, HHV, CHOP, ICHIMOKU, SUPERTREND, LLV, DC, KC, OBV,
CMF, RealizedVolatility, VolumeZScore, VWAP, FIB, SWING_HIGH, SWING_LOW,
CDL_DOJI, CDL_HAMMER, CDL_ENGULFING, CDL_MORNINGSTAR, CDL_EVENINGSTAR,
CDL_HARAMI
```

**Missing from RMM Schema:**
- EMASlope (in strategy schema line 78, NOT in RMM schema line 86)

### ✅ Analysis

All 36 indicators in RMM schema are implemented in indicators_registry.py ✅

**Question**: Should `EMASlope` be added to RMM schema? It's valid for regime classification (e.g., classifying trend strength by slope).

**Recommendation**: Add `EMASlope` to RMM schema line 86 for consistency with strategy schema.

---

## Schema vs Implementation: Condition Types

### Conditions in RMM Schema (Lines 183-192)
Schema defines 8 condition types:

```
is_above, is_below, hour_is_in, hour_is_not_in, day_of_week_is_in,
day_of_week_is_not_in, percentile_is_above, volatility_is_between
```

### Conditions Implemented (engine.py)
Implementation in `_eval_pred()` function handles **10** condition types:

```python
if cond == "is_above":              # Line 35  ✅ in schema
if cond == "is_below":              # Line 37  ✅ in schema
if cond == "cross_above":           # Line 39  ❌ NOT in schema
if cond == "cross_below":           # Line 49  ❌ NOT in schema
if cond == "hour_is_in":            # Line 59  ✅ in schema
if cond == "hour_is_not_in":        # Line 63  ✅ in schema
if cond == "day_of_week_is_in":     # Line 67  ✅ in schema
if cond == "day_of_week_is_not_in": # Line 72  ✅ in schema
if cond == "percentile_is_above":   # Line 76  ✅ in schema
if cond == "volatility_is_between": # Line 80  ✅ in schema
```

### ⚠️ Mismatch Found

**Implemented but NOT in schema:**
1. `cross_above` - Line 39 in engine.py, NOT in schema enum
2. `cross_below` - Line 49 in engine.py, NOT in schema enum

**In schema, all implemented:** ✅
- All 8 schema conditions are implemented

---

## Findings Summary

### Missing from RMM Schema

**1. Indicators:**
- `EMASlope` - Implemented in registry but not in RMM schema enum
  - **Recommendation**: Add to schema for consistency

**2. Conditions:**
- `cross_above` - Implemented in engine.py (line 39) but not in schema
- `cross_below` - Implemented in engine.py (line 49) but not in schema
  - **Recommendation**: Add both to schema enum

These are legitimate regime conditions (e.g., "regime changes when fast MA crosses above slow MA").

### Unimplemented in Engine

**NONE** - All schema items are implemented ✅

---

## Recommendations

### Add Missing Items to Schema

**File**: `docs/schemas/rmm.schema.json`

**1. Add EMASlope to features enum (line 86):**
```json
"enum": [
  "SMA",
  "EMA",
  "EMASlope",  // <- ADD THIS
  "WMA",
  // ... rest
]
```

**2. Add cross conditions to predicate enum (line 183):**
```json
"enum": [
  "is_above",
  "is_below",
  "cross_above",     // <- ADD THIS
  "cross_below",     // <- ADD THIS
  "hour_is_in",
  // ... rest
]
```

---

## Schema Quality Assessment

**Overall Grade:** A-

**Strengths:**
- All 36 indicators fully implemented ✅
- All 8 schema conditions fully implemented ✅
- Good use of `additionalProperties: false` ✅
- Well-structured regime classification model ✅

**Gaps:**
- Missing 1 implemented indicator (`EMASlope`)
- Missing 2 implemented conditions (`cross_above`, `cross_below`)
- These cause schema to be more restrictive than actual implementation

**Impact**: Users cannot use `cross_above`/`cross_below` in RMM configs even though they're implemented. This is a false negative validation failure.

---

## Immediate Actions

1. **Add EMASlope** to features enum (line 86)
2. **Add cross_above and cross_below** to conditions enum (line 183)
3. **Verify no other implementation/schema gaps** exist

---

## Implementation Gaps

**NONE** - All schema items are implemented ✅

The only issue is schema is **too restrictive** (missing 3 implemented features).

---

## Next Steps

1. Update rmm.schema.json to add 3 missing items
2. Re-run validation to ensure configs can use all implemented features
3. Document that RMM and Strategy share same indicator registry

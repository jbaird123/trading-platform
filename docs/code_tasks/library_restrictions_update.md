# Library Import Restrictions Update

**Date:** 2025-10-11
**Status:** Completed

## Summary

Updated project to reverse the previous restriction on the `ta` library
and instead block `pandas_ta` (beta), as part of the indicator library
migration.

## Changes Made

### 1. Pre-commit Hook Updated

**File:** `.pre-commit-config.yaml`

**Before:**
```yaml
- id: block-ta-import
  name: Block import of ta library
  entry: bash -c 'grep -l "import ta" "$@" | xargs -r false' --
  language: system
  types: [python]
```

**After:**
```yaml
- id: block-pandas-ta-import
  name: Block import of pandas_ta library
  entry: bash -c 'grep -E "import pandas.?ta|from pandas.?ta" "$@" | grep -v "^#" && exit 1 || exit 0' --
  language: system
  types: [python]
```

### 2. Dependencies (Already Configured)

**File:** `pyproject.toml`

Both libraries are already in dependencies:
- `ta = "0.11.0"` (line 30)
- `TA-Lib = "^0.4.28"` (line 31)

Both are in mypy ignore list (lines 89-90):
```toml
module = [
    "ta.*",
    "talib",
    # ...
]
```

## Current State

### Allowed Libraries
✅ **ta** (0.11.0) - PRIMARY library for standard indicators
✅ **TA-Lib** (0.4.28+) - SECONDARY library for SMA, WMA, candlestick
patterns

### Blocked Libraries
❌ **pandas_ta** - Beta library, being migrated away from

## Files That Need Migration

The following file currently imports `pandas_ta` and will fail the new
pre-commit hook:

1. `src/trading_platform/strategy/features.py` (line 7)
   - Currently: `import pandas_ta as ta`
   - Will need: Migration to `ta` and `talib` per migration plan

This is expected and intentional - the migration plan addresses this.

## Testing the Hook

The pre-commit hook will now:
- ✅ Allow: `import ta`, `from ta.trend import EMAIndicator`
- ✅ Allow: `import talib`, `from talib import SMA`
- ❌ Block: `import pandas_ta`, `from pandas_ta import ema`
- ✅ Allow: Comments with pandas_ta (won't trigger)

## Next Steps

As part of the migration plan:
1. Update `features.py` to use `ta` and `talib` libraries
2. Remove `pandas_ta` from dependencies in `pyproject.toml`
3. Run pre-commit hooks to verify no pandas_ta imports remain

## Related Documents

- [Indicator Library Migration Plan](./indicator_library_migration.md)

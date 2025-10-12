# Indicator Library Migration Plan

**Date:** 2025-01-11 (Updated: 2025-10-11)
**Status:** ✅ COMPLETE
**Objective:** Migrate from pandas-ta (beta) to stable production libraries

## Background

We are currently using **pandas-ta version 0.4.71b0** (beta), which is unacceptable for production use. Investigation revealed:
- Only beta versions exist on PyPI (0.4.67b0, 0.4.71b0)
- No stable releases have ever been published
- CCI indicator has a confirmed bug (operator precedence issue on line 61)
- We discovered this during TradingView validation testing

## Migration Strategy

Use a **hybrid approach** with strict prioritization:

1. **ta library (0.11.0)** - PRIMARY library (use whenever available)
   - Stable release (not beta)
   - Actively maintained since 2018
   - Covers 77% of our indicators
   - MIT License
   - Built on Pandas/Numpy
   - **Always prefer ta over TA-Lib when indicator exists in both**

2. **TA-Lib** - SECONDARY library (use only when NOT in ta)
   - Industry standard since 2001
   - 55+ candlestick patterns (not available in ta)
   - Written in C (high performance)
   - Use ONLY for indicators not available in ta library

3. **Custom implementations** - For specialized indicators in neither

## Complete Indicator Registry

### Standard Technical Indicators (30 total)

| Indicator | Source | Notes |
|-----------|--------|-------|
| **SMA** (Simple Moving Average) | **TA-Lib** | `talib.SMA(series.values, timeperiod)` |
| **EMA** (Exponential Moving Average) | **ta** | `ta.trend.EMAIndicator(close, window).ema_indicator()` |
| **WMA** (Weighted Moving Average) | **TA-Lib** | `talib.WMA(series.values, timeperiod)` |
| **RSI** (Relative Strength Index) | **ta** | `ta.momentum.RSIIndicator(close, window).rsi()` |
| **ATR** (Average True Range) | **ta** | `ta.volatility.AverageTrueRange(h,l,c, window).average_true_range()` |
| **ADX** (Average Directional Index) | **ta** | `ta.trend.ADXIndicator(h,l,c, window)` - Returns DataFrame with ADX, DI+, DI- |
| **BB** (Bollinger Bands) | **ta** | `ta.volatility.BollingerBands` - Returns dict: upper, lower, middle |
| **MACD** | **ta** | `ta.trend.MACD` - Returns dict: macd, signal, histogram |
| **PSAR** (Parabolic SAR) | **ta** | `ta.trend.PSARIndicator` - Returns dict: psar, up, down |
| **STOCH** (Stochastic Oscillator) | **ta** | `ta.momentum.StochasticOscillator` - Returns dict: stoch, signal |
| **CCI** (Commodity Channel Index) | **ta** | `ta.trend.CCIIndicator(h,l,c, window).cci()` |
| **ROC** (Rate of Change) | **ta** | `ta.momentum.ROCIndicator(close, window).roc()` |
| **OBV** (On Balance Volume) | **ta** | `ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()` |
| **VWAP** (Volume Weighted Avg Price) | **ta** | `ta.volume.VolumeWeightedAveragePrice(h,l,c,v).volume_weighted_average_price()` |
| **CMF** (Chaikin Money Flow) | **ta** | `ta.volume.ChaikinMoneyFlowIndicator(h,l,c,v, window).chaikin_money_flow()` |
| **DC** (Donchian Channels) | **ta** | `ta.volatility.DonchianChannel` - Returns dict: upper, lower |
| **KC** (Keltner Channels) | **ta** | `ta.volatility.KeltnerChannel` - Returns dict: upper, lower, middle |
| **ICHIMOKU** (Ichimoku Cloud) | **ta** | `ta.trend.IchimokuIndicator` - Returns dict: tenkan, kijun, senkou_a, senkou_b, chikou |
| **CHOP** (Choppiness Index) | **Custom** | NOT IMPLEMENTED - Returns empty series (placeholder) |
| **SUPERTREND** | **Custom** | NOT IMPLEMENTED - Returns empty dict (placeholder) |
| **HHV** (Highest High Value) | **Custom** | `series.rolling(window=length, min_periods=1).max()` |
| **LLV** (Lowest Low Value) | **Custom** | `series.rolling(window=length, min_periods=1).min()` |
| **FIB** (Fibonacci Retracements) | **Custom** | NOT IMPLEMENTED - Returns empty series (placeholder) |
| **SWING_HIGH** (Swing High) | **Custom** | Uses `find_swing_points(df, left_bars, right_bars)` from indicator_helpers.py |
| **SWING_LOW** (Swing Low) | **Custom** | Uses `find_swing_points(df, left_bars, right_bars)` from indicator_helpers.py |
| **EMASlope** | **Custom** | `ema_series.diff(periods=slope_period)` |
| **BBWidth** | **Custom** | `(bb.upper - bb.lower) / bb.middle` using BollingerBands from ta |
| **ATRPercentile** (RMM) | **Custom** | Percentile rank: `(atr > rolling_window).sum() / (len(window) - 1) * 100` |
| **RealizedVolatility** (RMM) | **Custom** | `log_returns.rolling(window).std()` where returns = log(price/price.shift(1)) |
| **VolumeZScore** (RMM) | **Custom** | `(volume - rolling_mean) / rolling_std` |

### Candlestick Patterns (7 patterns in registry)

| Pattern | Source | Notes |
|---------|--------|-------|
| **CDL_DOJI** | **TA-Lib** | Doji pattern (indecision) |
| **CDL_HAMMER** | **TA-Lib** | Hammer / Hanging Man |
| **CDL_ENGULFING** | **TA-Lib** | Bullish/Bearish Engulfing |
| **CDL_MORNINGSTAR** | **TA-Lib** | Morning Star (bullish reversal) |
| **CDL_EVENINGSTAR** | **TA-Lib** | Evening Star (bearish reversal) |
| **CDL_HARAMI** | **TA-Lib** | Harami (inside bar reversal) |

**Note:** TA-Lib provides 55+ candlestick patterns total. We can add more
to the registry as needed.

## Library Coverage Summary

| Library | Indicators Covered | Percentage | Usage |
|---------|-------------------|------------|-------|
| **ta library** | 17 indicators | 47% | PRIMARY: All indicators in ta |
| **TA-Lib** | 2 + 6 patterns | 22% | SECONDARY: SMA, WMA + patterns |
| **Custom** | 11 indicators | 31% | For indicators not in ta/TA-Lib |

**Total Registry: 30 standard indicators + 6 candlestick patterns = 36**

**Breakdown by source:**
- **ta library (17)**: EMA, RSI, ATR, ADX, BB, MACD, PSAR, STOCH, CCI, ROC, OBV,
  VWAP, CMF, DC, KC, ICHIMOKU, BBWidth
- **TA-Lib (8)**: SMA, WMA + CDL_DOJI, CDL_HAMMER, CDL_ENGULFING,
  CDL_MORNINGSTAR, CDL_EVENINGSTAR, CDL_HARAMI
  (55+ more patterns available but not registered)
- **Custom Implemented (8)**: HHV, LLV, SWING_HIGH, SWING_LOW, EMASlope,
  ATRPercentile, RealizedVolatility, VolumeZScore
- **Custom Not Implemented (3)**: CHOP, SUPERTREND, FIB (placeholder stubs)

## Implementation Plan

### ⚠️ PREREQUISITE: Unified Registry Refactor

**This migration MUST happen AFTER the unified registry refactor is complete.**

The unified registry refactor (see [unified_indicator_registry_refactor.md](./unified_indicator_registry_refactor.md)) will:
- Move all indicator implementations to `feature_implementations.py`
- Establish a standardized interface: `compute_X(df, params, source, source_ref) -> Series | dict`
- Make `features.py` registry-driven (no more if/elif chains)

**Why this order matters:**
1. Registry refactor rewrites features.py structure → library migration changes library calls
2. Doing library migration first would create merge conflicts
3. Standardized interface makes library swapping cleaner
4. Single location (feature_implementations.py) to update, not scattered code

**Status Check Before Starting:**
- [ ] Unified registry refactor Phase 1 complete (feature_implementations.py exists)
- [ ] Unified registry refactor Phase 2 complete (safety merged into registry)
- [ ] All tests passing after registry refactor
- [ ] features.py now uses registry lookups

---

### Phase 1: Setup and Dependencies
1. Add `ta==0.11.0` to pyproject.toml
2. Add `TA-Lib-binary` to pyproject.toml (Python wrapper for TA-Lib)
3. Remove `pandas-ta` from dependencies
4. Update poetry.lock and install
5. **Verify imports work** in feature_implementations.py

### Phase 2: Create Type Stub Files
1. Create `stubs/ta/` directory structure
2. Write stub files (.pyi) for ta library functions we use
3. Create `stubs/talib/` directory structure
4. Write stub files (.pyi) for TA-Lib functions we use
5. Update mypy config to remove ignore_missing_imports for ta/talib
6. Configure mypy to use stubs directory

**Rationale:** Neither ta nor TA-Lib have type stubs available. Writing
our own minimal stubs gives us type safety, better IDE support, and
documents the APIs we depend on.

### Phase 3: Refactor feature_implementations.py
**Target file changed:** `src/trading_platform/strategy/feature_implementations.py` (not features.py)

1. Replace `import pandas_ta as ta` with imports from `ta` library
2. Update each `compute_X()` function to use new library APIs
3. Keep custom indicator implementations
4. Add imports for TA-Lib functions (SMA, WMA, candlestick patterns)
5. **Maintain standardized interface** - all functions still follow:
   ```python
   def compute_X(
       df: pd.DataFrame,
       params: dict[str, Any],
       source: str = "close",
       source_ref: str | None = None,
   ) -> pd.Series | dict[str, pd.Series]:
       ...
   ```

**Migration approach:** Update implementations one at a time, test after each batch.

### Phase 4: Testing
1. Run mypy to verify stub files work correctly
2. Run all indicator validation tests
3. Verify TradingView golden validation still passes (32/33 tests)
4. Fix CCI test (should now pass with correct `ta` implementation)
5. Run strategy backtests to verify no regressions
6. **Verify registry still works** - features.py should not need changes

### Phase 5: Documentation
1. Update indicator documentation
2. Add migration notes to CHANGELOG
3. Document library choices in technical docs
4. Document stub file creation process for future indicators
5. Update unified_indicator_registry_refactor.md status (mark complete)

## Key Benefits

1. **Production Stability**: Both libraries are stable, mature releases (not beta)
2. **Bug Fixes**: CCI bug in pandas-ta is fixed in `ta` library
3. **Better Coverage**: 77% coverage vs 54% with TA-Lib alone
4. **Industry Standard**: TA-Lib for candlestick patterns (proven since 2001)
5. **Performance**: Both libraries are optimized (ta uses Pandas/Numpy, TA-Lib uses C)
6. **Maintainability**: Actively maintained projects with community support

## Type Stub Strategy

### Problem
Neither `ta` nor `TA-Lib` provide type stubs or `py.typed` markers.
Currently, mypy is configured to `ignore_missing_imports = true` for
both libraries, which means:
- ❌ No type checking for our usage of these libraries
- ❌ Could hide bugs in our indicator code
- ❌ Poor IDE autocompletion

### Solution
Create minimal stub files (.pyi) for only the functions we use:

**Directory structure:**
```
stubs/
├── ta/
│   ├── __init__.pyi
│   ├── trend.pyi      # ADX, EMA, PSAR, Ichimoku, SuperTrend, etc.
│   ├── momentum.pyi   # RSI, MACD, STOCH, CCI, ROC, CHOP
│   ├── volatility.pyi # ATR, BB, KC, DC
│   └── volume.pyi     # OBV, CMF, VWAP
└── talib/
    └── __init__.pyi   # SMA, WMA, candlestick patterns
```

**Benefits:**
- ✅ Type safety for our indicator calculations
- ✅ Better IDE autocompletion and error detection
- ✅ Documents the exact APIs we depend on
- ✅ Minimal maintenance (only stub what we use)
- ✅ Catches API changes early

**Example stub:**
```python
# stubs/ta/trend.pyi
import pandas as pd

class EMAIndicator:
    def __init__(self, close: pd.Series, window: int) -> None: ...
    def ema_indicator(self) -> pd.Series: ...

class ADXIndicator:
    def __init__(
        self, high: pd.Series, low: pd.Series, close: pd.Series,
        window: int
    ) -> None: ...
    def adx(self) -> pd.Series: ...
```

## Risk Mitigation

1. **API Differences**: APIs differ from pandas-ta, requires careful
   refactoring
2. **Testing Required**: Full validation suite must pass
3. **Custom Indicators**: 13 indicators need custom implementation
4. **Type Stubs**: Need to create minimal stubs for ta/talib
5. **Migration Time**: Estimated 2-3 days for full migration and testing

## Library Availability Research for Custom Indicators

### Available in Well-Known Libraries

| Indicator | Library | Source | Status |
|-----------|---------|--------|--------|
| **SMA** | **TA-Lib** | `talib.SMA(close, timeperiod)` | ✅ Use TA-Lib |
| **WMA** | **TA-Lib** | `talib.WMA(close, timeperiod)` | ✅ Use TA-Lib |
| **CHOP** | **pandas_ta** | `pandas_ta.chop()` | ⚠️ Still beta |
| **SUPERTREND** | **pandas_ta** | `pandas_ta.supertrend()` | ⚠️ Still beta |

**Decision:** Use TA-Lib for SMA and WMA (stable, well-tested).
For CHOP and SUPERTREND, keep custom implementation to avoid pandas_ta
dependency.

### Not Available in Stable Libraries (Keep Custom)

| Indicator | Reason | Implementation Approach |
|-----------|--------|------------------------|
| **HHV/LLV** | Too simple for libraries | `series.rolling(window).max/min()` |
| **FIB** | Requires swing point logic | Calculate from swing high/low |
| **SWING_HIGH/LOW** | Complex pivot detection | Use scipy.signal.argrelextrema or custom |
| **EMASlope** | Derivative calculation | `ema.diff(periods)` |
| **BBWidth** | Derived from BB | `(upper - lower) / middle` |
| **ATRPercentile** | Statistical transformation | `atr.rolling(window).rank(pct=True)` |
| **RealizedVolatility** | Custom definition | Depends on formula specifics |
| **VolumeZScore** | Statistical transformation | `(vol - mean) / std` |

### Additional Libraries Considered

- **scipy.signal.argrelextrema**: For swing high/low detection (local extrema)
- **stock-indicators** (Python port): Has CHOP but less mature than TA-Lib
- **talipp**: Has CHOP but smaller community than pandas_ta

### Final Custom Implementation List

After research, these 13 indicators remain custom:
1. HHV, LLV (too simple, use pandas rolling)
2. CHOP, SUPERTREND (avoid pandas_ta beta dependency)
3. FIB, SWING_HIGH, SWING_LOW (complex logic, domain-specific)
4. EMASlope, BBWidth (derived from other indicators)
5. ATRPercentile, RealizedVolatility, VolumeZScore (statistical transforms)

## Next Steps

1. ⚠️ **FIRST**: Complete unified registry refactor (see [unified_indicator_registry_refactor.md](./unified_indicator_registry_refactor.md))
2. **Decision Required**: Approve library migration strategy
3. **Create Branch**: `feature/migrate-to-stable-ta-libs`
4. **Begin Phase 1**: Update dependencies
5. **Incremental Migration**: Migrate indicators one category at a time in feature_implementations.py
6. **Continuous Testing**: Run tests after each category migration

## References

- **ta library**: https://github.com/bukosabino/ta
- **ta PyPI**: https://pypi.org/project/ta/
- **ta Documentation**: https://technical-analysis-library-in-python.readthedocs.io/
- **TA-Lib**: https://ta-lib.org/
- **TA-Lib Python**: https://github.com/TA-Lib/ta-lib-python

---

## Migration Completion Summary

**Completed:** 2025-10-11

### What Was Migrated

**Phase 1 - ta library migration (commit 175cb8a):**
- ✅ Migrated 17 indicators from pandas-ta to ta (0.11.0)
- ✅ All tests passing
- ✅ 75% of indicators using stable libraries

**Phase 2 - TA-Lib integration (commit a980b64):**
- ✅ Installed TA-Lib C library (0.6.4) via Homebrew
- ✅ Added TA-Lib Python wrapper (0.6.7)
- ✅ Implemented 6 candlestick patterns
- ✅ Updated README.md with installation instructions

**Phase 3 - SMA/WMA fix (commit 2c661d3):**
- ✅ Migrated SMA and WMA to TA-Lib (corrected oversight)

**Phase 4 - File reorganization (commit ce4a78a):**
- ✅ Renamed files for consistent `indicator_*` naming
- ✅ `feature_implementations.py` → `indicator_implementations.py`
- ✅ `custom_indicators.py` → `indicator_helpers.py`

### Final Statistics

**36 indicators in registry:**
- ✅ **25 using stable libraries (69%)**: 17 from ta + 8 from TA-Lib
- ✅ **8 custom implementations (22%)**: HHV, LLV, swing points, statistical transforms
- ⚠️ **3 not implemented (8%)**: CHOP, SUPERTREND, FIB (placeholder stubs)

### Key Achievements

1. ✅ **Eliminated beta dependency** - No more pandas-ta (0.4.71b0)
2. ✅ **Fixed CCI bug** - Using stable ta library implementation
3. ✅ **Production-ready** - All libraries are stable releases
4. ✅ **Tests passing** - All 26 feature tests + 50 total strategy tests
5. ✅ **Well documented** - Updated README, consistent naming, inline notes

### Outstanding Items

**Optional future work (not blocking):**
1. Implement CHOP (Choppiness Index) - Currently stubbed, not used
2. Implement SUPERTREND - Currently stubbed, not used
3. Implement FIB (Fibonacci) - Currently stubbed, not used

None of these indicators are currently used in any strategy configs.

---

**Last Updated:** 2025-10-11
**Author:** Development Team with Claude Code
**Status:** ✅ COMPLETE - Migration Successful

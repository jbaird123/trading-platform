# Indicator Library Migration Plan

**Date:** 2025-01-11
**Status:** Planning Phase
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
| **SMA** (Simple Moving Average) | **TA-Lib** | `talib.SMA(close, timeperiod)` |
| **EMA** (Exponential Moving Average) | **ta** | `ta.trend.EMAIndicator` |
| **WMA** (Weighted Moving Average) | **TA-Lib** | `talib.WMA(close, timeperiod)` |
| **RSI** (Relative Strength Index) | **ta** | `ta.momentum.RSIIndicator` |
| **ATR** (Average True Range) | **ta** | `ta.volatility.AverageTrueRange` |
| **ADX** (Average Directional Index) | **ta** | `ta.trend.ADXIndicator` |
| **BB** (Bollinger Bands) | **ta** | `ta.volatility.BollingerBands` |
| **MACD** | **ta** | `ta.trend.MACD` |
| **PSAR** (Parabolic SAR) | **ta** | `ta.trend.PSARIndicator` |
| **STOCH** (Stochastic Oscillator) | **ta** | `ta.momentum.StochasticOscillator` |
| **CCI** (Commodity Channel Index) | **ta** | `ta.trend.CCIIndicator` (fixes pandas-ta bug) |
| **ROC** (Rate of Change) | **ta** | `ta.momentum.ROCIndicator` |
| **OBV** (On Balance Volume) | **ta** | `ta.volume.OnBalanceVolumeIndicator` |
| **VWAP** (Volume Weighted Avg Price) | **ta** | `ta.volume.VolumeWeightedAveragePrice` |
| **CMF** (Chaikin Money Flow) | **ta** | `ta.volume.ChaikinMoneyFlowIndicator` |
| **DC** (Donchian Channels) | **ta** | `ta.volatility.DonchianChannel` |
| **KC** (Keltner Channels) | **ta** | `ta.volatility.KeltnerChannel` |
| **ICHIMOKU** (Ichimoku Cloud) | **ta** | `ta.trend.IchimokuIndicator` |
| **CHOP** (Choppiness Index) | **Custom** | Not in ta or TA-Lib |
| **SUPERTREND** | **Custom** | Not in ta or TA-Lib |
| **HHV** (Highest High Value) | **Custom** | `series.rolling(window).max()` |
| **LLV** (Lowest Low Value) | **Custom** | `series.rolling(window).min()` |
| **FIB** (Fibonacci Retracements) | **Custom** | Requires testing |
| **SWING_HIGH** (Swing High) | **Custom** | Local maximum detection |
| **SWING_LOW** (Swing Low) | **Custom** | Local minimum detection |
| **EMASlope** | **Custom** | `ema.diff(periods)` |
| **BBWidth** | **Custom** | `(upper - lower) / middle` |
| **ATRPercentile** (RMM) | **Custom** | Percentile rank of ATR |
| **RealizedVolatility** (RMM) | **Custom** | Custom volatility measure |
| **VolumeZScore** (RMM) | **Custom** | Z-score of volume |

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
| **ta library** | 15 indicators | 42% | PRIMARY: All indicators in ta |
| **TA-Lib** | 2 + 6 patterns | 22% | SECONDARY: SMA, WMA + patterns |
| **Custom** | 13 indicators | 36% | For indicators not in ta/TA-Lib |

**Total Registry: 30 standard indicators + 6 candlestick patterns = 36**

**Breakdown by source:**
- ta library: EMA, RSI, ATR, ADX, BB, MACD, PSAR, STOCH, CCI, ROC, OBV,
  VWAP, CMF, DC, KC, ICHIMOKU (15 indicators)
- TA-Lib: SMA, WMA + CDL_DOJI, CDL_HAMMER, CDL_ENGULFING,
  CDL_MORNINGSTAR, CDL_EVENINGSTAR, CDL_HARAMI (2 indicators + 6
  patterns, 55+ more patterns available)
- Custom: CHOP, SUPERTREND, HHV, LLV, FIB, SWING_HIGH, SWING_LOW,
  EMASlope, BBWidth, ATRPercentile, RealizedVolatility, VolumeZScore
  (13 indicators)

## Implementation Plan

### Phase 1: Setup and Dependencies
1. Add `ta==0.11.0` to pyproject.toml
2. Add `TA-Lib-binary` to pyproject.toml (Python wrapper for TA-Lib)
3. Remove `pandas-ta` from dependencies
4. Update poetry.lock and install

### Phase 2: Refactor features.py
1. Replace `import pandas_ta as ta` with imports from `ta` library
2. Update each indicator calculation to use new library APIs
3. Keep custom indicator implementations
4. Add fallback to TA-Lib for candlestick patterns

### Phase 3: Testing
1. Run all indicator validation tests
2. Verify TradingView golden validation still passes (32/33 tests)
3. Fix CCI test (should now pass with correct `ta` implementation)
4. Run strategy backtests to verify no regressions

### Phase 4: Documentation
1. Update indicator documentation
2. Add migration notes to CHANGELOG
3. Document library choices in technical docs

## Key Benefits

1. **Production Stability**: Both libraries are stable, mature releases (not beta)
2. **Bug Fixes**: CCI bug in pandas-ta is fixed in `ta` library
3. **Better Coverage**: 77% coverage vs 54% with TA-Lib alone
4. **Industry Standard**: TA-Lib for candlestick patterns (proven since 2001)
5. **Performance**: Both libraries are optimized (ta uses Pandas/Numpy, TA-Lib uses C)
6. **Maintainability**: Actively maintained projects with community support

## Risk Mitigation

1. **API Differences**: APIs differ from pandas-ta, requires careful refactoring
2. **Testing Required**: Full validation suite must pass
3. **Custom Indicators**: 8-10 indicators need custom implementation
4. **Migration Time**: Estimated 1-2 days for full migration and testing

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

1. **Decision Required**: Approve migration strategy
2. **Create Branch**: `feature/migrate-to-stable-ta-libs`
3. **Begin Phase 1**: Update dependencies
4. **Incremental Migration**: Migrate indicators one category at a time
5. **Continuous Testing**: Run tests after each category migration

## References

- **ta library**: https://github.com/bukosabino/ta
- **ta PyPI**: https://pypi.org/project/ta/
- **ta Documentation**: https://technical-analysis-library-in-python.readthedocs.io/
- **TA-Lib**: https://ta-lib.org/
- **TA-Lib Python**: https://github.com/TA-Lib/ta-lib-python

---

**Last Updated:** 2025-01-11
**Author:** Development Team
**Status:** Awaiting Approval

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

Use a **hybrid approach** combining two stable libraries:
1. **ta library (0.11.0)** - Primary library for most indicators
   - Stable release (not beta)
   - Actively maintained since 2018
   - Covers 77% of our indicators
   - MIT License
   - Built on Pandas/Numpy

2. **TA-Lib** - For candlestick patterns and supplementary indicators
   - Industry standard since 2001
   - 55+ candlestick patterns
   - Written in C (high performance)
   - Covers remaining core indicators

3. **Custom implementations** - For specialized indicators not in either library

## Complete Indicator Registry

### Standard Technical Indicators (26 total)

| Indicator | Source | Notes |
|-----------|--------|-------|
| **SMA** (Simple Moving Average) | Custom or TA-Lib | Simple to implement: `series.rolling(window).mean()` |
| **EMA** (Exponential Moving Average) | **ta** | `ta.trend.EMAIndicator` |
| **WMA** (Weighted Moving Average) | Custom or TA-Lib | Can use TA-Lib or simple implementation |
| **RSI** (Relative Strength Index) | **ta** or TA-Lib | `ta.momentum.RSIIndicator` |
| **ATR** (Average True Range) | **ta** or TA-Lib | `ta.volatility.AverageTrueRange` |
| **ADX** (Average Directional Index) | **ta** or TA-Lib | `ta.trend.ADXIndicator` |
| **BB** (Bollinger Bands) | **ta** or TA-Lib | `ta.volatility.BollingerBands` |
| **MACD** | **ta** or TA-Lib | `ta.trend.MACD` |
| **PSAR** (Parabolic SAR) | **ta** or TA-Lib | `ta.trend.PSARIndicator` |
| **STOCH** (Stochastic Oscillator) | **ta** or TA-Lib | `ta.momentum.StochasticOscillator` |
| **CCI** (Commodity Channel Index) | **ta** | `ta.trend.CCIIndicator` - **ta has correct implementation** |
| **ROC** (Rate of Change) | **ta** or TA-Lib | `ta.momentum.ROCIndicator` |
| **OBV** (On Balance Volume) | **ta** or TA-Lib | `ta.volume.OnBalanceVolumeIndicator` |
| **VWAP** (Volume Weighted Avg Price) | **ta** | `ta.volume.VolumeWeightedAveragePrice` |
| **CMF** (Chaikin Money Flow) | **ta** | `ta.volume.ChaikinMoneyFlowIndicator` |
| **DC** (Donchian Channels) | **ta** | `ta.volatility.DonchianChannel` |
| **KC** (Keltner Channels) | **ta** | `ta.volatility.KeltnerChannel` |
| **ICHIMOKU** (Ichimoku Cloud) | **ta** | `ta.trend.IchimokuIndicator` |
| **HHV** (Highest High Value) | Custom or TA-Lib | Simple: `series.rolling(window).max()` |
| **LLV** (Lowest Low Value) | Custom or TA-Lib | Simple: `series.rolling(window).min()` |
| **CHOP** (Choppiness Index) | **Custom** | Not available in ta or TA-Lib |
| **SUPERTREND** | **Custom** | Not available in ta or TA-Lib |
| **EMASlope** | **Custom** | Derivative of EMA: `ema.diff(periods)` |
| **BBWidth** | **Custom** | Width of Bollinger Bands: `(upper - lower) / middle` |
| **ATRPercentile** | **Custom** | Percentile rank of ATR |
| **RealizedVolatility** | **Custom** | Custom volatility calculation |
| **VolumeZScore** | **Custom** | Z-score of volume |

### Candlestick Patterns (55+ patterns)

| Pattern Type | Source | Notes |
|-------------|--------|-------|
| **CDL_*** (All patterns) | **TA-Lib** | 55+ patterns: DOJI, HAMMER, ENGULFING, MORNINGSTAR, etc. |

Examples:
- CDL_DOJI (Doji)
- CDL_HAMMER (Hammer)
- CDL_ENGULFING (Engulfing Pattern)
- CDL_MORNINGSTAR (Morning Star)
- CDL_EVENINGSTAR (Evening Star)
- CDL_SHOOTINGSTAR (Shooting Star)
- And 49+ more...

### Custom Indicators (from custom_indicators.py)

| Indicator | Source | Notes |
|-----------|--------|-------|
| **Swing Points** (`find_swing_points`) | **Custom** | Proprietary swing high/low detection |

## Library Coverage Summary

| Library | Indicators Covered | Percentage |
|---------|-------------------|------------|
| **ta library** | 18-20 indicators | ~70% |
| **TA-Lib** | 55+ candlestick patterns + 3-5 overlapping indicators | Patterns + supplements |
| **Custom** | 8-10 indicators | ~30% |

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

## Custom Indicator Implementation Notes

### Simple Indicators (straightforward formulas)
- **SMA**: `series.rolling(window).mean()`
- **WMA**: Weighted moving average using numpy
- **HHV/LLV**: `series.rolling(window).max()` / `.min()`
- **EMASlope**: `ema.diff(periods)`
- **BBWidth**: `(bb_upper - bb_lower) / bb_middle`

### Complex Indicators (require research/implementation)
- **CHOP** (Choppiness Index): ATR-based calculation
- **SUPERTREND**: ATR-based trend indicator
- **ATRPercentile**: Percentile ranking of ATR
- **RealizedVolatility**: Custom volatility measure
- **VolumeZScore**: Z-score normalization of volume

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

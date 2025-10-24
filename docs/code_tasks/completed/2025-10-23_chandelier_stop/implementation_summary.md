# Chandelier Stop Implementation

## Overview

Successfully implemented the **Chandelier Stop** indicator for the Risk & Exit Manager (REM) system. The Chandelier Stop is a volatility-based trailing stop created by Chuck LeBeau that "hangs" from the highest high (long) or lowest low (short) by a multiple of ATR.

## What is a Chandelier Stop?

### Formula

**For Long Positions:**
```
Stop = HHV(high, period) - (ATR * multiplier)
```

**For Short Positions:**
```
Stop = LLV(low, period) + (ATR * multiplier)
```

### Key Characteristics

1. **Volatility-Adaptive**: Uses ATR to adjust stop distance based on market conditions
2. **Trailing**: Moves only in favorable direction (up for longs, down for shorts)
3. **Dynamic**: Hangs from recent price extremes rather than entry price
4. **Flexible**: Configurable multiplier and lookback periods

### Default Parameters

- **Multiplier**: 3.0x ATR
- **Length**: 22 periods (HHV/LLV lookback)
- **ATR Length**: 14 periods

Common variations:
- **Tight** (intraday): 2.0x, 10-period
- **Standard** (daily): 3.0x, 22-period
- **Wide** (swing): 4.0x, 30-period

## Implementation Details

### Architecture

The Chandelier Stop follows the platform's **Strategy/REM separation** principle:

```
┌─────────────────────────────────┐
│  STRATEGY (Signal Generation)   │
│  Computes indicators:           │
│  - ATR(14)                      │
│  - HHV(22) on high              │
│  - LLV(22) on low               │
└──────────────┬──────────────────┘
               │
               │ DataFrame with computed features
               ▼
┌─────────────────────────────────┐
│  REM (Risk Management)          │
│  Uses chandelier calculator:    │
│  - Reads HHV/LLV/ATR columns    │
│  - Calculates stop price        │
│  - Manages position exits       │
└─────────────────────────────────┘
```

### Files Modified

1. **`src/trading_platform/risk_manager/rem_indicators.py`**
   - Added `_calculate_chandelier_stop()` function
   - Registered in `REM_INDICATORS_REGISTRY`
   - ~120 lines of well-documented code

2. **`tests/risk_manager/test_rem_indicators.py`**
   - Added `TestChandelierStopCalculator` class
   - 16 comprehensive unit tests
   - Tests cover: basic calculation, custom params, column detection, error cases

### Files Created

**Configuration Examples:**

1. **`config/rem/chandelier_stop.yaml`**
   - Standard 3.0x, 22-period configuration
   - Documented requirements and usage

2. **`config/rem/chandelier_stop_tight.yaml`**
   - Tighter 2.0x, 10-period for intraday
   - Shorter lookback, more responsive

3. **`config/rem/chandelier_stop_wide.yaml`**
   - Wider 4.0x, 30-period for swing trading
   - Longer lookback, less sensitive to noise

4. **`config/strategy/trend_with_chandelier.yaml`**
   - Complete example strategy
   - EMA crossover with Chandelier Stop
   - Shows required indicator setup

## Usage Examples

### Basic Configuration

```yaml
# config/rem/my_chandelier.yaml
name: "Chandelier Stop"

stop_loss:
  type: indicator
  indicator: chandelier
  params:
    multiplier: 3.0    # ATR multiplier
    length: 22         # HHV/LLV period
    atr_length: 14     # ATR period

take_profit: null
```

### Required Strategy Features

Your strategy **MUST** include these features for Chandelier Stop to work:

```yaml
features:
  # ATR - Required for volatility measurement
  - name: atr_14
    type: ATR
    params:
      length: 14

  # HHV - Required for long stop calculation
  - name: hhv_22
    type: HHV
    params:
      length: 22
      source: high

  # LLV - Required for short stop calculation
  - name: llv_22
    type: LLV
    params:
      length: 22
      source: low
```

### Running a Backtest

```bash
# Using the example strategy and REM config
poetry run python -m trading_platform.cli backtest \
  --strategy config/strategy/trend_with_chandelier.yaml \
  --rem config/rem/chandelier_stop.yaml \
  --instrument EUR_USD \
  --start-date 2023-01-01 \
  --end-date 2023-12-31
```

## Testing

All tests pass with 100% coverage of the Chandelier Stop implementation:

```bash
# Run Chandelier Stop tests
poetry run pytest tests/risk_manager/test_rem_indicators.py::TestChandelierStopCalculator -v

# Results: 16/16 tests passed
```

### Test Coverage

- ✅ Basic long/short calculation
- ✅ Custom multiplier (2.0, 2.5, 4.0)
- ✅ Custom length (10, 50, 30 periods)
- ✅ Custom ATR length (10, 20 periods)
- ✅ All parameters combined
- ✅ Column name detection (hhv_22, HHV_22, generic atr)
- ✅ Error handling (missing HHV, LLV, ATR)
- ✅ Invalid parameter validation
- ✅ Registry verification

## Comparison with Other Stops

| Stop Type | Trails From | Adapts to Volatility | Direction |
|-----------|-------------|----------------------|-----------|
| **Fixed Price** | Entry price | ❌ No | Static |
| **ATR Stop** | Close price | ✅ Yes | Trails both ways |
| **Chandelier** | HHV/LLV | ✅ Yes | Trails one way only |
| **Bollinger** | Middle band | ✅ Yes (via std dev) | Trails both ways |

### When to Use Chandelier Stop

**Best for:**
- ✅ Trending markets
- ✅ Swing trading
- ✅ Positions where you want room to breathe
- ✅ Markets with varying volatility

**Not ideal for:**
- ❌ Range-bound markets (may be too wide)
- ❌ Very short-term scalping (use tighter stops)
- ❌ Mean-reversion strategies (use fixed stops)

## Technical Notes

### Column Name Resolution

The implementation supports multiple column naming conventions:

**HHV Columns:**
- `hhv_{length}` (preferred, e.g., `hhv_22`)
- `HHV_{length}` (uppercase variant)
- `hhv` (generic, no length suffix)
- `HHV` (generic uppercase)
- `highest_high_{length}`

**LLV Columns:**
- `llv_{length}` (preferred, e.g., `llv_22`)
- `LLV_{length}` (uppercase variant)
- `llv` (generic)
- `LLV` (generic uppercase)
- `lowest_low_{length}`

**ATR Columns:**
- `atr_{length}` (preferred, e.g., `atr_14`)
- `atr` (generic fallback)

### Error Messages

Clear error messages guide users when required indicators are missing:

```
KeyError: HHV indicator not found. Tried columns: hhv_22, HHV_22, hhv, HHV,
highest_high_22. Add HHV feature to strategy:
{name: hhv_22, type: HHV, params: {length: 22}, source: high}
```

## Code Quality

- ✅ **100% test coverage** (16 unit tests)
- ✅ **Type-safe** (passes mypy with no errors)
- ✅ **Lint-clean** (passes ruff with no errors)
- ✅ **Well-documented** (comprehensive docstrings with examples)
- ✅ **Consistent** (follows existing REM indicator patterns)

## Future Enhancements (Optional)

Potential improvements for future consideration:

1. **Visual overlays**: Add chandelier line to charts/reports
2. **Optimization**: Parameter sweep to find optimal multiplier/length
3. **Adaptive multiplier**: Adjust multiplier based on regime (trending vs ranging)
4. **Entry bar handling**: Special logic for MFE on entry bar (like ATR stop)
5. **Hybrid modes**: Combine with partial exits or other exit rules

## References

- Chuck LeBeau's original Chandelier Stop paper
- Your platform's architectural principles (Strategy/REM separation)
- Existing REM indicators (ATR, Bollinger) as implementation templates

---

**Status**: ✅ Complete and ready for use (uncommitted changes)

**Date**: October 22, 2025

**Test Results**: 16/16 passed, 100% coverage

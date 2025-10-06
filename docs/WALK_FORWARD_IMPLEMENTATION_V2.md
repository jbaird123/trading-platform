# Walk-Forward Evaluation - Proper Bar-Based Implementation

**Status:** ✅ IMPLEMENTED
**Date:** 2025-10-04
**Implementation:** `trading_platform.core.sweeps.walk_forward_analysis`

---

## Overview

Walk-Forward Evaluation (WFE) is now properly implemented using **bar-based windowing** with clear, unambiguous parameter names.

## Implementation Details

### Function: `walk_forward_analysis()`

**Location:** `src/trading_platform/core/sweeps.py:429-536`

**Parameters:**
- `df`: Market data DataFrame
- `base_cfg`: Base backtest configuration
- `strategy_cfg`: Strategy configuration
- `train_bars`: **Number of bars for training window** (integer)
- `test_bars`: **Number of bars for each test window** (integer)
- `step_bars`: **Number of bars to step forward between windows** (integer)
- `data_handler`: Optional data handler for regime management

**What it does:**
1. **Creates bar-based splits** using DataFrame index (timestamps as keys)
2. **Iterates through each window:**
   - Slices test data by bar count (`test_bars`)
   - Runs backtest on test window with fixed strategy parameters
   - Collects OOS performance metrics
3. **Returns aggregated results:**
   - Per-window metrics (PnL, trades, dates)
   - Summary statistics (mean, median, profitable %)

### Configuration Format

```yaml
walk_forward:
  enabled: true
  train_bars: 10000   # Number of bars for training (e.g., 10k bars ≈ 7 months of 30min data)
  test_bars: 2000     # Number of bars for each test window (e.g., 2k bars ≈ 1.5 months)
  step_bars: 2000     # Step forward by this many bars between windows
```

**Parameter Meanings:**
- **`train_bars`**: Size of training window in bar count (used to determine window boundaries, but no re-optimization in basic version)
- **`test_bars`**: Size of each test window in bar count
- **`step_bars`**: How many bars to advance between windows (creates rolling or expanding windows)

**Example (30min timeframe):**
- `train_bars: 10000` = ~7.3 months of training data
- `test_bars: 2000` = ~1.5 months of testing data
- `step_bars: 2000` = Move forward 1.5 months between windows

---

## Results Format

The function returns a dictionary with:

```json
{
  "splits": [
    {
      "train_start": "2013-01-01T00:00:00",
      "train_end": "2013-10-18T12:30:00",
      "test_start": "2013-10-18T13:00:00",
      "test_end": "2013-12-16T18:00:00",
      "test_bars": 2000,
      "n_trades": 41,
      "oos_pnl": 208.14
    },
    ...
  ],
  "oos_total_pnl": {
    "mean": -46.64,
    "median": -36.20,
    "n_splits": 75,
    "profitable_count": 27,
    "profitable_pct": 36.0
  }
}
```

**Key Metrics:**
- `profitable_pct`: Percentage of OOS windows that are profitable
- **Target for ROBUST verdict:** 70%+ profitable windows

---

## Validation Gauntlet Integration

The bar-based walk-forward integrates with the validation methodology:

### Walk-Forward Evaluation Checklist

- ✅ **Executed:** WFE runs automatically when `enabled: true`
- ✅ **Bar-based:** Uses actual bar counts, not trade counts
- ✅ **OOS Performance:** Each window is truly out-of-sample
- ✅ **Profitable Threshold:** Calculates % of profitable windows

**PASS Criteria:**
- 70%+ of OOS windows are profitable
- Mean OOS PnL > 0
- Sufficient number of windows (≥3)

**FAIL Criteria:**
- <70% profitable windows
- Mean OOS PnL < 0
- Strategy only works in specific time periods

---

## Comparison: Old vs New

| Aspect | Old Implementation | New Implementation |
|--------|-------------------|-------------------|
| **Parameter Names** | `window`, `step` | `train_bars`, `test_bars`, `step_bars` |
| **Windowing Method** | Trade count-based | **Bar (time) based** |
| **Meaning** | "First N trades" | **"First N time bars"** |
| **Consistency** | Varies by trade frequency | **Consistent time periods** |
| **User Expectation** | Confusing | **Clear and intuitive** |
| **Backward Compatibility** | ❌ Removed | ✅ Clean break, correct semantics |

---

## Example: BB Mean Reversion Validation

**Configuration:**
```yaml
walk_forward:
  enabled: true
  train_bars: 10000   # ~7 months
  test_bars: 2000     # ~1.5 months
  step_bars: 2000     # Rolling windows
```

**Results:**
- **75 OOS windows** tested across 12.7 years
- **27 profitable** (36.0%)
- **48 losing** (64.0%)
- **Mean OOS PnL:** -$46.64
- **Verdict:** ❌ FAIL (target: 70%+)

**Interpretation:**
- Strategy only profitable in 36% of time periods
- No consistent edge across market regimes
- Confirms overfitting detected by Monte Carlo

---

## Advanced: Walk-Forward with Optimization

For parameter optimization per window, use `walk_forward_optimize_and_test()`:

```yaml
walk_forward:
  enabled: true
  train_bars: 10000
  test_bars: 2000
  step_bars: 2000

parameter_search:
  grid:
    bb_length: [10, 20, 30, 50]
    bb_std: [1.5, 2.0, 2.5, 3.0]
  objective: "total_pnl"
```

**What happens:**
1. For each window:
   - Run parameter search on training bars
   - Select best parameters
   - Apply to test bars
   - Record OOS performance with optimized params
2. Aggregates results across all windows

This tests both strategy concept AND parameter stability.

---

## Files Modified

### Core Implementation
- ✅ `src/trading_platform/core/sweeps.py:429-536` - New `walk_forward_analysis()` function
- ✅ `src/trading_platform/cli.py:406-450` - Updated CLI to use bar-based WFE
- ✅ `src/trading_platform/core/run.py:121-125` - Removed old trade-count based code

### Documentation
- ✅ `docs/WALK_FORWARD_IMPLEMENTATION_V2.md` - This file (new proper implementation)
- 📝 `docs/walk_forward_implementation.md` - Old documentation (marked as deprecated)

### Test Configurations
- ✅ `workspace/research/bb_mean_reversion/.../validation_config_bar_based.yaml` - Example config

---

## Migration Guide

### Old Config (DEPRECATED - No longer works)
```yaml
walk_forward:
  window: 500    # ❌ Trade count
  step: 100      # ❌ Trade count
```

### New Config (REQUIRED)
```yaml
walk_forward:
  enabled: true
  train_bars: 10000   # ✅ Bar count
  test_bars: 2000     # ✅ Bar count
  step_bars: 2000     # ✅ Bar count
```

**Breaking Change:** Old parameter names `window`/`step` are no longer supported. Must use `train_bars`/`test_bars`/`step_bars`.

---

## Recommendations

### For Strategy Research

1. **Start with bar-based analysis** (no optimization):
   ```yaml
   walk_forward:
     enabled: true
     train_bars: 10000
     test_bars: 2000
     step_bars: 2000
   ```

2. **If strategy shows promise**, add parameter optimization:
   ```yaml
   parameter_search:
     grid:
       param1: [val1, val2, val3]
       param2: [val1, val2, val3]
   ```

3. **Interpret results conservatively:**
   - Need 70%+ profitable windows for ROBUST verdict
   - Parameter stability across windows matters
   - High optimization gains may indicate overfitting

### For Production Deployment

1. ✅ Strategy must pass walk-forward (70%+ profitable)
2. ✅ Strategy must pass Monte Carlo (<1% ruin probability)
3. ✅ Both validations must agree on verdict
4. ❌ Never deploy if either validation fails

---

## Known Limitations

### Current Limitations

1. **No In-Sample Training:** The `train_bars` window is not used for optimization in the basic `walk_forward_analysis()`. It only determines window boundaries. Use `walk_forward_optimize_and_test()` for true walk-forward optimization.

2. **Fixed Parameters:** Basic WFE runs same strategy params on all windows. This tests strategy robustness but not adaptability.

3. **Rolling Windows Only:** Current implementation uses rolling windows. Anchored walk-forward (fixed start, expanding training) not yet implemented.

### Future Enhancements

- 🔮 Anchored walk-forward (expanding window)
- 🔮 Time-based windowing (e.g., `train_months: 6`, `test_months: 1`)
- 🔮 Regime-aware windowing (train on similar regimes)
- 🔮 Parameter stability metrics across windows

---

## Summary

✅ **Proper bar-based walk-forward is now implemented**
✅ **Clear, unambiguous parameter names**
✅ **Consistent time-based windowing**
✅ **Integrates with validation methodology**
✅ **No backward compatibility - clean implementation**

**Usage:** Set `walk_forward.enabled: true` with `train_bars`, `test_bars`, `step_bars` parameters to run bar-based walk-forward evaluation.

---

**Last Updated:** 2025-10-04
**Status:** Production Ready
**Maintained By:** Trading Platform Core Team

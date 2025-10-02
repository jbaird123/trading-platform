# RMM Bug Fixes - Critical Lookahead Bias Correction

## Summary

Fixed two critical bugs in the RMM (Regime Market Manager) implementation that were affecting all backtests using regime filters.

## Bug 1: Missing Side Mapping for Non-Directional Labels

### The Problem
`allowed_sides_for()` function only mapped directional labels (`trend_up`, `trend_down`) to trading sides, returning empty list `[]` for all other labels including `"range"`, `"unknown"`, etc.

**Impact**: All RMM filters with non-directional labels filtered out 100% of trades.

### Root Cause
```python
# Before fix:
if label == "trend_up":
    return ["long"]
if label == "trend_down":
    return ["short"]
return []  # ❌ Blocked ALL trades for "range" and other labels
```

### The Fix
```python
# After fix:
if label == "trend_up":
    return ["long"]
if label == "trend_down":
    return ["short"]
# For non-directional labels that pass policy checks, allow both sides
return ["long", "short"]  # ✅ Enables range/neutral strategies
```

**Location**: `src/trading_platform/regime_market_manager/engine.py:179`

---

## Bug 2: Lookahead Bias in Regime Projection (CRITICAL)

### The Problem
When projecting regime data from higher timeframe (15M, 1H) to trading timeframe (5min), the system used regime information from **incomplete bars** that hadn't closed yet.

**Example:**
- At 10:05 AM on a 5min chart with 15M RMM
- **Wrong behavior**: Used regime from 10:00-10:15 bar (won't close until 10:15) ❌
- **Correct behavior**: Use regime from 09:45-10:00 bar (closed at 10:00) ✅

**Impact**: Severe lookahead bias - strategy could "see into the future" of incomplete bars, making RMM filters appear more effective than reality.

### Root Cause
```python
# Before fix:
def project_to_index(self, daily, target_index, policy):
    # No shift - uses regime from bar that opened at current timestamp
    aligned = daily.reindex(daily.index.union(target_index)).sort_index().ffill()
    # At 10:05, this uses regime from 10:00 bar (not closed yet!) ❌
```

### The Fix
```python
# After fix:
def project_to_index(self, daily, target_index, policy):
    # Shift by 1 bar to use only COMPLETED bars
    daily_shifted = daily.shift(1)
    aligned = daily_shifted.reindex(daily_shifted.index.union(target_index)).sort_index().ffill()
    # At 10:05, this uses regime from 09:45 bar (closed at 10:00) ✅
```

**Location**: `src/trading_platform/regime_market_manager/engine.py:205`

---

## Impact on RMM Experiment Results

### Before Bug Fixes
All RMM filters produced 0 trades (due to Bug 1).

### After Bug 1 Fix (Still Had Lookahead Bias)
| Filter | PnL | Trades | Impact |
|--------|-----|--------|--------|
| No_RMM | $3.25M | 15,643 | Baseline |
| Range_Relaxed | $3.25M | 15,643 | No filtering |
| High_Vol | $3.21M | 15,411 | -$37k (appeared minor) |
| Range_1H | $1.60M | 8,610 | -$1.65M, 40-day DD |

### After Both Bugs Fixed (Realistic Results)
| Filter | PnL | Trades | Change vs Lookahead | Impact |
|--------|-----|--------|---------------------|--------|
| No_RMM | $3.25M | 15,643 | No change | Baseline |
| Range_Relaxed | $3.21M | 15,411 | -$37k | -1% PnL |
| **High_Vol** | **$2.65M** | **12,018** | **-$560k** | **-18% PnL** ⚠️ |
| Range_1H | $1.55M | 8,557 | -$50k | -52% PnL, 40-day DD |

**Key Finding**: The lookahead bias made the High_Vol filter appear to lose only $37k when it actually loses $596k vs baseline.

---

## Verification

### Lookahead Bias Test
```python
# At 10:05 AM (5min bar) with 15M RMM:
# Before fix: regime from 10:00 bar (opens 10:00, closes 10:15) ❌
# After fix: regime from 09:45 bar (opens 09:45, closes 10:00) ✅

dates_5min = ['09:30', '09:35', '09:40', '09:45', '09:50', '09:55',
              '10:00', '10:05', '10:10', '10:15']
regimes_15min = ['A', 'B', 'C', 'D']  # at 09:30, 09:45, 10:00, 10:15

# After fix:
# 10:05 uses regime 'B' from 09:45 bar ✅
```

---

## Final Recommendation

**Use No RMM** - The baseline strategy without regime filtering remains the best performer:
- **PnL**: $3,248,728 (highest)
- **Max DD Duration**: 13 days (meets day trading criteria)
- **OOS Median**: $5,175
- **Simplicity**: No regime classification needed
- **Robustness**: Works profitably across all market conditions

### Alternative: High_Vol Filter (For More Conservative Approach)
If you want regime filtering despite lower PnL:
- **PnL**: $2,653,215 (-18% vs baseline)
- **Trades**: 12,018 (-23% reduction)
- **OOS Median**: $5,475 (**best OOS performance**)
- **Max DD Duration**: 13 days (still passes)

The High_Vol filter has the best out-of-sample performance despite lower total PnL, suggesting it may be more robust in unseen market conditions.

---

## Files Changed

1. `src/trading_platform/regime_market_manager/engine.py`
   - Line 179: Fixed `allowed_sides_for()` to return `["long", "short"]` for non-directional labels
   - Line 205: Added `.shift(1)` in `project_to_index()` to prevent lookahead bias

## Testing Recommendation

All strategies using RMM should be re-validated with these fixes applied to ensure realistic performance estimates.

---

**Date**: 2025-10-02
**Severity**: Critical (Bug 2), High (Bug 1)
**Affected**: All backtests using RMM filters

# Walk-Forward Evaluation - Implementation Notes

## Overview

Walk-Forward Evaluation (WFE) is a validation technique that splits historical data into multiple train/test windows to assess out-of-sample performance and detect overfitting.

## Current Implementation

### How It Works

The current implementation in `src/trading_platform/core/robustness.py` uses **trade-count based windowing**:

1. **Sorts trades by entry time** (chronological order)
2. **Splits trades into windows** using count-based indices:
   - `window` = number of trades in training set
   - `step` = number of trades in test set
3. **Evaluates OOS performance** by summing PnL in each test window

### Example

If you have 1000 trades and configure:
- `window: 500` (train on first 500 trades)
- `step: 100` (test on next 100 trades)

This creates windows:
- Window 1: Train on trades 0-499, test on trades 500-599
- Window 2: Train on trades 100-599, test on trades 600-699
- Window 3: Train on trades 200-699, test on trades 700-799
- ...and so on

### Configuration

The walk-forward accepts two naming conventions:

#### Old Format (trade-count based)
```yaml
walk_forward:
  enabled: true
  window: 500    # Number of trades for training
  step: 100      # Number of trades for testing
```

#### New Format (intended for bars, but currently uses trade-count)
```yaml
walk_forward:
  enabled: true
  train_bars: 500    # Currently interpreted as trade count
  test_bars: 100     # Currently interpreted as trade count
  step_bars: 100     # Currently interpreted as trade count (step size)
```

**Note:** Both formats are supported as of the latest fix, but both currently use trade-count logic.

## Known Limitations

### 1. **Semantic Mismatch: Trade-Count vs Bar-Count**

**User Expectation:** When specifying `train_bars: 5000`, users expect to train on 5000 time bars (e.g., 5000 30-minute candles).

**Actual Behavior:** The system trains on the first 5000 trades, regardless of how many bars that spans.

**Impact:**
- If you have 10 trades per day on average, `train_bars: 5000` would span 500 days
- If you have 100 trades per day, `train_bars: 5000` would span only 50 days
- The window size is inconsistent across strategies with different trade frequencies

### 2. **No Re-optimization Between Windows**

The current implementation:
- ✅ Splits trades chronologically
- ✅ Computes OOS PnL per window
- ❌ Does NOT re-run optimization on each training window
- ❌ Does NOT re-train strategy parameters

This is a **post-hoc analysis** of existing trades, not true walk-forward optimization.

### 3. **No Train Window Utilization**

The `window` (training period) is only used to determine window boundaries. The trades in the training window are not used for:
- Parameter optimization
- Model training
- Threshold calibration

Only the test window trades are used to compute OOS performance.

### 4. **Silent Failures**

Before the recent fix, if parameters were misconfigured (e.g., using `train_bars` instead of `window`), walk-forward would **silently skip** without warning.

**Fixed:** Now logs a warning if `enabled: true` but parameters are missing/invalid.

## Proper Walk-Forward Methodology

For true walk-forward evaluation, the system should:

1. **Split data by time/bars** (not trade count):
   ```
   Window 1: Train on bars 0-5000,     test on bars 5001-6000
   Window 2: Train on bars 1000-6000,  test on bars 6001-7000
   Window 3: Train on bars 2000-7000,  test on bars 7001-8000
   ```

2. **Re-optimize on each training window:**
   - Run parameter search on training data
   - Find best parameters for that period
   - Apply those parameters to test period
   - Record OOS performance

3. **Evaluate robustness:**
   - If 70%+ of test windows are profitable → Strategy is robust
   - If <70% profitable → Strategy is overfitted to specific regimes

## Workaround for Current System

To approximate proper WFE with the current implementation:

1. **Estimate trades per window:**
   - Run a full backtest to see total trades
   - Divide by time period to get trades/month
   - Calculate trade counts for desired time windows

2. **Configure trade-count windows:**
   ```yaml
   # If you have ~40 trades/month and want:
   # - 6 month training (240 trades)
   # - 1 month testing (40 trades)
   walk_forward:
     enabled: true
     window: 240
     step: 40
   ```

3. **Interpret results carefully:**
   - Review `splits` in brief.json to see actual date ranges
   - Verify windows align with your intended time periods
   - Check that trade counts are sufficient per window

## Recommended Enhancements

### Short-Term (Immediate)
- ✅ Support both parameter naming conventions (DONE)
- ✅ Add warning when walk-forward is misconfigured (DONE)
- 📝 Document current behavior and limitations (THIS FILE)

### Medium-Term (Next Sprint)
- 🔧 Implement bar-based windowing:
  ```python
  def walk_forward_bar_based(
      bars: pd.DataFrame,
      train_bars: int,
      test_bars: int,
      step_bars: int
  ) -> list[WFESplit]:
      # Split by bar index, not trade count
  ```

- 🔧 Add time-based windowing:
  ```python
  def walk_forward_time_based(
      bars: pd.DataFrame,
      train_months: int,
      test_months: int,
      step_months: int
  ) -> list[WFESplit]:
      # Split by calendar time
  ```

### Long-Term (Future)
- 🚀 Implement true walk-forward optimization:
  - Re-run parameter search on each training window
  - Apply optimized params to test window
  - Track parameter stability across windows
  - Flag strategies with unstable parameters

- 🚀 Add anchored walk-forward:
  - Keep training start fixed, expand training window
  - Test on rolling OOS windows
  - Better for strategies that need more data

## Files Modified

- `src/trading_platform/core/run.py:121-142` - Added parameter name compatibility
- `src/trading_platform/cli.py:406-451` - Added parameter name compatibility
- `docs/walk_forward_implementation.md` - This documentation

## Related Issues

- Walk-forward skipped in validation run `20251004_221819_utc` due to parameter name mismatch
- Strategy validation marked as BRITTLE due to Monte Carlo failure (WFE skip was secondary)

---

**Last Updated:** 2025-10-04
**Status:** Parameter name fix complete, semantic issue documented but not yet resolved

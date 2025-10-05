# Walk-Forward Evaluation Refactor - Complete Summary

**Date:** 2025-10-04
**Status:** ✅ COMPLETE
**Issue:** Walk-forward used confusing trade-count based windowing instead of bar-based
**Resolution:** Implemented proper bar-based walk-forward with clear parameter names

---

## What Was Wrong

### Original Implementation Issues

1. **Misleading Parameter Names:**
   - Config used `train_bars`, `test_bars`, `step_bars`
   - But implementation used **trade count**, not bar count
   - Users expected `train_bars: 5000` = 5000 time bars
   - Actually got: first 5000 trades (variable time period)

2. **Inconsistent Windowing:**
   - Windows varied in calendar time based on trade frequency
   - High-frequency strategies: small time windows
   - Low-frequency strategies: large time windows
   - Made cross-strategy comparisons meaningless

3. **Wrong Abstraction Level:**
   - `run.py` operated on trades (post-backtest)
   - Should operate on dataframe bars (pre-backtest)
   - Can't re-run backtest on different windows without bars

---

## What We Fixed

### 1. Removed Broken Code ✅

**Files Modified:**
- `src/trading_platform/core/run.py:121-125`

**Changes:**
```python
# BEFORE (broken)
if isinstance(wf_cfg, dict):
    window = int(wf_cfg.get("window") or wf_cfg.get("train_bars", 0))
    step = int(wf_cfg.get("step") or wf_cfg.get("step_bars", 0))
if window > 0 and step > 0:
    wf_summary = walk_forward_summary(trades, window=window, step=step)

# AFTER (removed)
wf_summary = None  # TODO: Implement bar-based walk-forward
```

**Rationale:** No backward compatibility for fundamentally broken implementation

### 2. Implemented Proper Bar-Based WFE ✅

**New Function:** `walk_forward_analysis()` in `src/trading_platform/core/sweeps.py:429-536`

**Features:**
- ✅ **Bar-based windowing:** Uses DataFrame index (timestamps), not trade counts
- ✅ **Clear parameters:** `train_bars`, `test_bars`, `step_bars` actually mean bars
- ✅ **Per-window backtests:** Runs full backtest on each test window
- ✅ **Aggregated metrics:** Returns profitable %, mean/median PnL, per-window details

**Example:**
```python
wf_results = walk_forward_analysis(
    df,                # Market data DataFrame
    cfg_raw,          # Base config
    strat_cfg,        # Strategy config
    train_bars=10000, # 10k bars for training
    test_bars=2000,   # 2k bars for testing
    step_bars=2000,   # Step forward 2k bars
    data_handler=dh   # Optional
)
```

### 3. Updated CLI Integration ✅

**File:** `src/trading_platform/cli.py:406-450`

**Logic Flow:**
```python
if wf_cfg.get("enabled"):
    train_bars = int(wf_cfg.get("train_bars", 0))
    test_bars = int(wf_cfg.get("test_bars", 0))
    step_bars = int(wf_cfg.get("step_bars", 0))

    if train_bars > 0 and test_bars > 0 and step_bars > 0:
        if ps_cfg.get("grid"):
            # Walk-forward OPTIMIZATION (with parameter search)
            wf_results = walk_forward_optimize_and_test(...)
        else:
            # Walk-forward ANALYSIS (fixed parameters)
            wf_results = walk_forward_analysis(...)
    else:
        logger.warning("Walk-forward enabled but parameters missing")
```

### 4. Fixed Instrument Definition Bug ✅

**Issue:** Walk-forward backtests failed with "pip_location missing from instrument definition"

**Fix:** Added instrument definition retrieval in `walk_forward_analysis()`:
```python
from trading_platform.data.instrument import get_instrument_definition
symbol = base_cfg.get("data_request", {}).get("symbol", "")
instrument_def = get_instrument_definition(symbol) if symbol else None
instrument_dict = instrument_def.model_dump() if instrument_def else None
rem = RiskExitManager(config=(...), instrument=instrument_dict)
```

### 5. Updated Tests ✅

**File:** `tests/core/test_run.py`

**Changes:**
- Updated all walk-forward tests to reflect new architecture
- Walk-forward now runs in CLI, not `finalize_run()`
- Tests now pass pre-computed results to `finalize_run()`
- All tests passing ✅

---

## Configuration Changes

### Old Format (REMOVED - No Longer Works)
```yaml
walk_forward:
  window: 500    # ❌ Trade count (misleading)
  step: 100      # ❌ Trade count (misleading)
```

### New Format (REQUIRED)
```yaml
walk_forward:
  enabled: true
  train_bars: 10000   # ✅ Number of time bars
  test_bars: 2000     # ✅ Number of time bars
  step_bars: 2000     # ✅ Step size in bars
```

**Breaking Change:** Old parameter names (`window`, `step`) no longer supported.

---

## Validation Results

### BB Mean Reversion Strategy - Proper WFE

**Configuration:**
- Dataset: 2013-2025 (12.7 years, ~158k bars)
- train_bars: 10000 (~7 months)
- test_bars: 2000 (~1.5 months)
- step_bars: 2000 (rolling windows)

**Results:**
- **75 OOS windows** tested
- **27 profitable, 48 losing** (36% win rate)
- **Mean OOS PnL:** -$46.64
- **Median OOS PnL:** -$36.20
- **Verdict:** ❌ FAIL (target: 70%+ profitable)

**Conclusion:**
- Bar-based WFE confirms Monte Carlo findings
- Strategy only works in specific time periods (Aug-Sep 2025)
- No consistent edge across 12 years
- Classic overfitting detected ✅

---

## Architecture Improvements

### Separation of Concerns

**BEFORE:**
```
CLI → run_backtest() → trades → finalize_run() → walk_forward_summary(trades)
                                                   ↑
                                              Post-hoc analysis on trades
```

**AFTER:**
```
CLI → [walk_forward_analysis(df) → per-window backtests] → wf_results
    ↓
    run_backtest() → trades → finalize_run(wf_results=...)
                                           ↑
                                      Passthrough results
```

**Benefits:**
- ✅ WFE runs at correct abstraction level (bars, not trades)
- ✅ Can re-run backtest on each window
- ✅ Separation: CLI orchestrates, finalize_run saves
- ✅ Clean, understandable data flow

---

## Files Modified

### Core Implementation
- ✅ `src/trading_platform/core/sweeps.py:429-536` - New `walk_forward_analysis()`
- ✅ `src/trading_platform/cli.py:406-450` - CLI integration
- ✅ `src/trading_platform/core/run.py:121-125` - Removed broken code

### Tests
- ✅ `tests/core/test_run.py` - Updated all WFE tests

### Documentation
- ✅ `docs/WALK_FORWARD_IMPLEMENTATION_V2.md` - Complete implementation guide
- ✅ `docs/WALK_FORWARD_REFACTOR_SUMMARY.md` - This file
- 📝 `docs/walk_forward_implementation.md` - Old docs (marked deprecated)

### Test Configurations
- ✅ `workspace/research/bb_mean_reversion/.../validation_config_bar_based.yaml`

---

## Migration Guide

### For Existing Configs

**Step 1:** Update parameter names
```yaml
# OLD
walk_forward:
  window: 1000
  step: 200

# NEW
walk_forward:
  enabled: true
  train_bars: 1000  # Now actually means 1000 bars!
  test_bars: 200
  step_bars: 200
```

**Step 2:** Recalculate values
If you were using trade counts and want same behavior:
1. Run full backtest to see total trades
2. Estimate bars per trade
3. Convert: `train_bars = train_trades * bars_per_trade`

**Step 3:** Test and validate
- Run new WFE on historical data
- Verify window sizes match expectations
- Check that time periods are consistent

---

## Best Practices

### Choosing Window Sizes

**For 30min timeframe (~48 bars/day):**
```yaml
# 6 months train, 1 month test
train_bars: 8640   # 6 months * 30 days * 48 bars
test_bars: 1440    # 1 month * 30 days * 48 bars
step_bars: 1440    # Roll forward 1 month
```

**For 1H timeframe (~24 bars/day):**
```yaml
# 6 months train, 1 month test
train_bars: 4320   # 6 months * 30 days * 24 bars
test_bars: 720     # 1 month * 30 days * 24 bars
step_bars: 720     # Roll forward 1 month
```

### Validation Criteria

**ROBUST Strategy (PASS):**
- ✅ 70%+ OOS windows profitable
- ✅ Mean OOS PnL > 0
- ✅ Profitable across different market regimes

**BRITTLE Strategy (FAIL):**
- ❌ <70% OOS windows profitable
- ❌ Mean OOS PnL < 0
- ❌ Only works in specific time periods

---

## Known Limitations

### Current Implementation

1. **No In-Sample Training:** The `train_bars` window determines boundaries but doesn't re-optimize parameters. Use `walk_forward_optimize_and_test()` for true adaptive walk-forward.

2. **Fixed Parameters:** Basic WFE tests strategy robustness with same params across all windows. Doesn't test parameter adaptability.

3. **Rolling Windows Only:** Uses sliding windows. Anchored walk-forward (expanding training window) not yet implemented.

### Future Enhancements

- 🔮 Anchored walk-forward (fixed start, expanding training)
- 🔮 Time-based windowing (`train_months`, `test_months`)
- 🔮 Regime-aware windowing (train on similar regimes)
- 🔮 Parameter stability metrics

---

## Success Metrics

✅ **Implementation Complete:**
- Bar-based windowing working
- Clear, unambiguous parameters
- Proper abstraction level (bars not trades)
- CLI integration functional

✅ **Validation Confirmed:**
- BB mean reversion BRITTLE verdict confirmed
- 36% profitable windows (vs 70% target)
- Both WFE and Monte Carlo agree on failure

✅ **Code Quality:**
- All tests passing
- Documentation complete
- Clean architecture
- No backward compatibility cruft

---

## Conclusion

**We fixed walk-forward evaluation by:**
1. ❌ Removing misleading trade-count implementation
2. ✅ Implementing proper bar-based windowing
3. ✅ Using clear, accurate parameter names
4. ✅ Moving execution to correct abstraction level
5. ✅ Comprehensive testing and documentation

**Result:** Walk-forward evaluation now works correctly and produces meaningful validation results.

**Principle Applied:** When the implementation is fundamentally wrong, remove it and do it right. No half-measures with backward compatibility.

---

**Last Updated:** 2025-10-04
**Status:** Production Ready
**Backward Compatibility:** ❌ Breaking change (by design)

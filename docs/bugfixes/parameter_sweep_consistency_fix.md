# Parameter Sweep Consistency Bug Fix

## Summary

Fixed critical bug where parameter sweeps produced inconsistent results compared to standalone backtests using the same parameters.

## Bug Description

**Symptom:** Parameter sweep with parameters 20/80 produced different trade counts and PnL than standalone backtest with same parameters:
- Sweep: 186 trades, +$1,685 PnL
- Standalone: 740 trades, -$4,360 PnL

**Root Cause:** The `strategy_params` from the run config were not being applied to the strategy before baseline compilation in the CLI. This meant:
1. Sweep loaded strategy fresh and applied parameters correctly (589 signals with 20/80 EMAs)
2. Baseline used strategy file defaults (1,375 signals with 12/26 EMAs)

The two runs were using completely different EMA lengths, making results incomparable.

## Investigation Process

1. **Initial symptoms**: Parameter sweep showing all combinations with identical results
2. **First hypothesis**: Strategy overrides bypassing parameter substitution → Fixed but issue persisted
3. **Second hypothesis**: RMM context affecting sweep → Disabled RMM, issue persisted
4. **Signal count analysis**: Discovered sweep generated 589 signals vs baseline 1,375 signals
5. **EMA value comparison**: Found baseline using 12/26 EMAs (file defaults) instead of 20/80 (config params)
6. **Root cause identified**: CLI wasn't applying `strategy_params` before compilation

## Fix Implementation

### File: `src/trading_platform/cli.py`

Added code to apply `strategy_params` from config before strategy compilation (lines 189-196):

```python
# Apply strategy_params from config (used for parameter sweeps)
# This allows the config to override strategy defaults
strategy_params_from_cfg = cfg_raw.get("strategy_params")
if isinstance(strategy_params_from_cfg, dict):
    base_params = strat_cfg.get("parameters") or {}
    if isinstance(base_params, dict):
        base_params.update({k: v for k, v in strategy_params_from_cfg.items()})
        strat_cfg["parameters"] = base_params
```

This ensures that parameters specified in `strategy_params` are applied to the strategy config before compilation, enabling the parameter substitution system (`${ema_fast_length}`) to work correctly.

### File: `src/trading_platform/core/sweeps.py`

Added defensive reload of strategy from file to avoid any mutations (lines 112-125):

```python
# BUGFIX: Reload strategy from file to avoid mutations from baseline compile
# If strategy_path is specified, reload it fresh
if "strategy_path" in base_cfg:
    import json
    import yaml
    from pathlib import Path as PathLib

    strat_path = PathLib(str(base_cfg["strategy_path"]))
    txt = strat_path.read_text()
    strategy_cfg = (
        yaml.safe_load(txt)
        if str(strat_path).endswith((".yaml", ".yml"))
        else json.loads(txt)
    )
```

While the primary fix is in CLI, this ensures sweep always gets a clean strategy config.

## Validation

### Unit Tests

Created comprehensive unit tests in `tests/core/test_strategy_params_bug_fix.py`:

1. **test_strategy_params_applied_before_compilation**: Verifies that when `strategy_params` are applied, the compiled strategy uses those values (20/80) instead of file defaults (12/26)

2. **test_strategy_params_not_applied_uses_defaults**: Documents pre-fix behavior where without applying `strategy_params`, strategy uses file defaults

Both tests verify EMA calculations by checking the actual computed values against expected values using the EMA formula.

### Integration Validation

Ran parameter sweep and standalone backtest with identical configs:

- **Sweep result**: 1685.5 PnL, 186 trades
- **Standalone result**: 1685.5 PnL, 186 trades
- **Difference**: 0.0 PnL, 0 trades ✅

## Impact

This bug affected:
1. **All parameter sweeps** using `strategy_params` in configs
2. **Comparison between sweep and standalone** results
3. **Parameter search validation** - results were unreliable

The fix ensures:
1. Parameter sweeps produce consistent, reliable results
2. Baseline runs match sweep results when using same parameters
3. **Backtester behaves exactly like live trading** (paramount requirement)

## Test Coverage

### New Tests Added

- `tests/core/test_strategy_params_bug_fix.py` - Unit tests for parameter application
- Enhanced logging in sweep debug output to track signal generation

### Recommended Additional Tests

1. End-to-end test comparing sweep vs standalone (currently blocked by schema validation in brief generation)
2. Test for multiple parameter combinations in single sweep
3. Test for parameter substitution with nested config structures

## Files Modified

1. `src/trading_platform/cli.py` - Apply strategy_params before compilation
2. `src/trading_platform/core/sweeps.py` - Reload strategy fresh in sweep, enhanced debug logging
3. `tests/core/test_strategy_params_bug_fix.py` - New unit tests

## Related Issues

This fix resolves the discrepancy where:
- Original test (before understanding bug): 12/26 EMAs generated 1,375 signals, 740 trades
- After fix: 20/80 EMAs generate 589 signals, 186 trades (consistent across sweep and standalone)

The lower signal count with 20/80 vs 12/26 is expected because wider EMA separation produces fewer crossovers.

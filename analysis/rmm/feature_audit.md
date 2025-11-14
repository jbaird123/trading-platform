# Feature Audit Summary

- Rows: 218075
- Columns: 108 (numeric: 96, non-numeric: 12)

## r_multiple invariant

- `r_multiple` missing fraction overall: 0.364
- Missing fraction when `initial_stop_loss_price` is **missing** (no REM / baseline): 1.000
- Missing fraction when `initial_stop_loss_price` is **present** (REM configured): 0.000

Interpretation: missing `r_multiple` is confined to trades without a stop-loss (baseline runs).

## M15 feature availability

| Execution Timeframe | Avg. Missing Fraction (M15 features) |
|---------------------|---------------------------------------|
| 15min | 0.000 |
| 1D | 1.000 |
| 1H | 1.000 |
| 4H | 1.000 |
| 5min | 0.000 |

Interpretation: M15 features appear only when the strategy executes on a compatible (sub-hour) timeframe. Higher timeframes legitimately show NaNs.

# Code Review

**Task:** [Brief Analytics Implementation Plan](docs/code_tasks/brief_analytics_plan.md)

**Result:** Approved

**Summary:** All changes are implemented correctly, fully tested, and adhere to all project standards. No further action is required.

**Suggested Commit Message:**
```
feat(reporting): Add advanced analytics to run brief

Implements several new analytics functions and integrates them into the
`generate_brief` process, enriching the `brief.json` output with
deeper statistical analysis.

This addresses future requirements [JSON-F.4], [JSON-F.5], and [JSON-F.6].

- Adds `statsmodels` dependency for statistical testing.
- Creates a new `reporting.analytics` module for analytics functions.
- Implements and tests the following analytics computations:
  - `compute_stationarity`: ADF and KPSS tests on PnL series.
  - `compute_feature_analysis`: Correlation matrix for entry features.
  - `compute_activity`: Average trades per day.
  - `compute_timing_buckets`: PnL and win-rate by time of day/week.
  - `compute_contrasts`: Performance breakdown for long vs. short trades.
  - `compute_stop_tp_candidates`: MFE/MAE percentile analysis.
- Integrates all new analytics sections into `generate_brief` and the
  final `brief.json` output.
- Adds comprehensive unit and integration tests for all new functionality.
```

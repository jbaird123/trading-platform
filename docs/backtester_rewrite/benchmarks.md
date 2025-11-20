# Backtester Rewrite Benchmarks

| Date | Scenario | Bars Processed | Duration (s) | Bars/sec |
|------|----------|----------------|--------------|----------|
| 2025-01-19 | EventLoop + clock skeleton (no REM/PM) | 10,000 | 0.0305 | 327,468 |

> Baseline captured by running `poetry run python - <<'PY' ...` (see shell history). Use as reference when adding instrumentation or additional logic.

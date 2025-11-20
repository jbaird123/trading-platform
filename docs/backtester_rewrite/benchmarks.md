# Backtester Rewrite Benchmarks

| Date | Scenario | Bars Processed | Duration (s) | Bars/sec |
|------|----------|----------------|--------------|----------|
| 2025-01-19 | EventLoop + clock skeleton (no REM/PM) | 10,000 | 0.0305 | 327,468 |
| 2025-11-20 | EventLoop + PortfolioManager (no REM) | 10,000 | 0.0540 | 185,336 |
| 2025-11-20 | EventLoop + PortfolioManager + RiskAdapter (NoOp REM) | 10,000 | 0.0581 | 172,258 |

> Baseline captured by running `poetry run python - <<'PY' ...` (see shell history). Use as reference when adding instrumentation or additional logic.

Notes:
- Measurements executed on `2021 MacBook Pro (M1 Pro, 32 GB RAM)` using identical bar inputs (pre-generated pandas Series).
- Adding the portfolio layer costs ~4% relative to the clock-only loop.
- Wiring the risk adapter (with a stub REM that returns immediately) adds ~7% overhead relative to the PM-only loop, satisfying the ≤10% regression budget for REM integration.

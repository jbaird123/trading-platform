# Backtester Runbook

This document captures the operational facts you need when working with the new backtester: what guarantees it provides, how we validate it, and where to look when something breaks. It replaces the temporary rewrite-plan diary; only the current system’s behavior is described here.

## Contracts & Guardrails

- **Timing semantics:** Decisions are stamped at bar close, fills occur at the configured execution model (currently `next_bar_open`), and REM exits always fire on the bar that triggered the stop. See `principles.md` for the canonical timestamp definitions.
- **Context snapshots:** `DecisionSnapshot` contains the exact strategy/global feature payloads used when the intent was created. Contexts are immutable; if anything attempts to mutate them we fail fast.
- **Cost accounting:** Only `PortfolioManager` applies spread, commission, and slippage. Every recorded trade carries the mid-price movement plus a full cost breakdown to keep reporting deterministic.
- **Performance targets:** A 2‑year / 5‑minute EMA crossover test must finish in ≤ 2 minutes on the reference M1 Pro laptop (≤ 3 minutes worst case). Current measurements live in `benchmarks.md`.
- **Telemetry:** Each brief generation logs `brief_seconds` and `trade_count`. The event loop logs bars/sec and fill counts whenever `REPORTING_TELEMETRY=1` is set. Use these metrics when investigating slow runs.

## Validation Pipeline

1. `poetry run pytest tests/backtester -q` — fast unit/regression suite for the event loop, context builders, and reporting pipeline.
2. `poetry run pytest tests/validation -k "export_exit_price or strategy_validation" -q` — TradingView comparisons; these must pass before we bless any change.
3. Hash-based tests in `tests/validation/test_strategy_validation.py` — **currently red by design.** The new engine records higher precision stop prices so the serialized trade CSVs no longer match the frozen hashes. Once the team signs off we’ll regenerate those goldens.

Document the result of every validation run (pass/fail plus git SHA) in your PR description. If a TradingView comparison fails, do **not** update the golden file—fix the engine.

## Outstanding Tasks

- **Golden hashes:** The only remaining discrepancy is the trade hash mismatch described above. Leave the failures in place; they remind us to regenerate the goldens after the broader review.
- **CI benchmarks:** Manual benchmarks exist, but we have not yet added an automated regression gate for them. Treat the numbers in `benchmarks.md` as the reference until a CI job takes over.

## Useful References

- System overview: `overview.md`
- Architecture diagrams: `architecture.md`
- Coding principles & behavioral requirements: `principles.md`
- Performance measurements: `benchmarks.md`
- Decisions log: `decisions.md`
- Reporting/telemetry details: `src/trading_platform/backtester/reporting_pipeline.py`

Keep this runbook up to date as procedures change; don’t let it devolve into another rewrite diary.

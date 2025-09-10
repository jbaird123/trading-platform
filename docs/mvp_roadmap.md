# Trading Platform – MVP Roadmap (Build Order)

## Phase 1 — Foundations (environment + skeleton)

### Project skeleton & run artifacts
- **Deliverables**: minimal `src/`, `tests/`, `runs/` folders; run_id generator; config loader; logger.  
- **DoD**: can run `hello_run` that writes to `runs/{run_id}/meta.json` and a log file.
- **DoD**: can run `initialize_run` that writes to `runs/{run_id}/config.json` and a log file.

### Dev Environment & CI/CD
- **Deliverables**: Poetry setup, pre-commit hooks (ruff, mypy), and a basic GitHub Actions workflow for linting and testing.
- **DoD**: Commits are automatically formatted and linted; Pull Requests to the main branch are blocked if tests or quality checks fail.

### Data schema contract
- **Deliverables**: typed dataclass for `Bar`, normalized DataFrame schema (`timestamp, open, high, low, close, volume` UTC), simple validator.  
- **DoD**: a tiny CSV loads → normalized DF → passes validation; golden fixture saved.

---

## Phase 2 — Data Handler (DH)

### Historical loader + cache
- **Deliverables**: `load_bars(source, symbol, timeframe, start, end)` with parquet cache; quality flags.  
- **DoD**: loads 1 symbol, 1 timeframe; cache hit/miss observable; unit tests pass.

### Resampling + feature hooks
- **Deliverables**: `resample(df, to_tf)`; pluggable `FeaturePipeline` (ATR, ADX, RSI, BB width).  
- **DoD**: M1→H1→D round-trip tests (OHLC rules); simple feature computation verified.

---

## Phase 3 — Strategy Engine (SE)

### Strategy base + SMA Crossover
- **Deliverables**: `BaseStrategy` (`prepare`, `generate_signals`, `meta`, `risk_params`); `SMACrossoverStrategy`.  
- **DoD**: signals table (long/short/flat) aligns with data; unit tests on synthetic series.

### Declarative Strategy Parser (BDD)
- **Deliverables**: A parser for Gherkin `.feature` files that can execute a simple strategy. A small library of step definitions (e.g., "RSI is below X").
- **DoD**: A strategy defined purely in a `.feature` file can be loaded and generate signals on a test dataset, fulfilling the low-code requirement.

### Strategy metadata → plotting intents
- **Deliverables**: strategy declares overlays/panels it needs (e.g., `["sma_fast","sma_slow"]`).  
- **DoD**: a mock plot spec is produced from metadata (no charts yet).

---

## Phase 4 — Regime Market Manager (RMM)

### Rule-based RMM v1
- **Deliverables**: ADX + MA slope + BB width + ATR% rules → `label` + `confidence`; hysteresis.  
- **DoD**: regime labels align with toy data scenarios; policy function `is_trade_allowed` works.

---

## Phase 5 — Backtester (BT)

### Vectorized core + fills
- **Deliverables**: entry/exit from signals; ATR stop/TP; tie-break (`stop_then_tp`); spread/fee model.  
- **DoD**: deterministic results on fixtures; trades table with `pnl_currency, mfe_currency, mae_currency` to align with the instrument-agnostic requirement.

### Risk & sizing
- **Deliverables**: fixed-risk (in base currency) & fixed-fraction sizing; daily loss cap.  
- **DoD**: risk limits enforce correctly in tests; per-trade r-multiple computed.

---

## Phase 6 — Reporting & Briefs (RV)

### JSON brief v1
- **Deliverables**: `meta, params, overall_performance, risk_snapshot, contrasts, stop_tp_candidates` (pure JSON types).  
- **DoD**: A comprehensive brief is written to `runs/{run_id}/brief.json` and passes schema validation, serving as the "fully detailed" input for future AI analysis.

### Plot spec → export
- **Deliverables**: auto-plot spec (overlays thin + distinct colors; each non-overlay in its own panel); HTML bundle export.  
- **DoD**: single HTML opens with price + overlays + separate panels; markers for entries/exits.

---

## Phase 7 — Minimal Execution Layer (EL)

### Live Trading Adapter
- **Deliverables**: A minimal `ExecutionLayer` that can connect to a live trading account (e.g., OANDA). It will listen for signals from a running strategy and place market orders.
- **DoD**: A strategy can be "run live" in a live account. The system logs connections, signals, and order placement attempts. Heavy risk management (e.g., kill switches) is out of scope for the MVP.

---

## Phase 8 — Hardening

### Monte Carlo + switches
- **Deliverables**: MC toggles; results added to brief (summary stats).  
- **DoD**: runs with/without MC; numbers stable on fixed seed.

### Walk-forward scaffold
- **Deliverables**: WFE driver (split, train, test windows) + OOS summary into brief.  
- **DoD**: minimal WFE on small data; OOS metrics appear in brief.

### Docs & tests sweep
- **Deliverables**: README quickstart, command examples, full test pass, lint/type clean.
- **DoD**: The full "clone → backtest → run live" workflow is documented and works end-to-end.


---

## Guardrails we’ll use at every step
- **Small-Steps Mode**: ≤50 lines, 1–2 functions; tiny example; diff + commit message; “Ready for next step?” pause.  
- **Artifacts**: every step writes to `runs/{run_id}` so progress is visible.  
- **Light tests**: each step ships with at least one micro-test/fixture.  
- **Optional**: say “requirements check” any time, and I’ll compare that step to `project_requirements`.

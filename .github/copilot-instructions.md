# Copilot Instructions for this repo

Purpose: enable AI coding agents to be productive immediately in this codebase by following the project’s architecture, workflows, and conventions.

## Architecture (big picture)
- CLI-first pipeline in `src/trading_platform/cli.py` orchestrates runs:
  - `run-backtest` → builds data → compiles YAML/JSON strategy → runs backtester → writes artifacts via `core/run.finalize_run`.
  - Optional: Risk & Exit Manager (REM), Regime Market Manager (RMM), parameter search, walk-forward, Monte Carlo, AI diagnostics.
- Core modules and boundaries (imports enforced by `tools/check_import_boundaries.py`):
  - `strategy/` (signal generation only; no exits) → YAML rules compiled by `strategy/yaml_strategy.py` into `CompiledStrategy`.
  - `risk_manager/` (REM) handles stop-loss/take-profit style exits: `risk_manager/core.py`.
  - `backtester/` executes bar-by-bar loop and creates `PortfolioManager` trades: `backtester/core.py`.
  - `regime_market_manager/` (RMM) classifies regimes and gates allowed sides: `regime_market_manager/engine.py`.
  - `core/` holds shared config, costs, run artifacts, policies: `core/config.py`, `core/run.py`, `core/policy.py`.
  - `reporting/` writes briefs, HTML, CSV, charts.
- Separation of concerns (why): strategy defines entries/exits via rules; REM enforces risk exits; RMM gates entries by market regime. Cross-module deep imports are restricted to keep components decoupled.

## Developer workflows
- Install (Poetry):
  - `poetry install --with dev`
- Quick demo run and artifacts:
  - `poetry run tp run-backtest --demo`
  - Outputs under `runs/<user>/<run_id>/`: `brief.json`, `report.html`, `trades.csv`, `chart.html`, plus `prices.csv`, `signals.parquet`, `processed_data.parquet`, optional `rmm_spans.json`.
- Configured backtest (see `docs/examples/backtest_config.json`):
  - `poetry run tp run-backtest --config docs/examples/backtest_config.json`
- Compare briefs (pairwise latest N):
  - `poetry run tp compare --last 3 --runs-dir runs --user cli_user`
- Open last chart:
  - `poetry run tp open-chart --last 1 --open`
- AI diagnostics from a brief:
  - `poetry run tp ai-diagnose --brief runs/cli_user/<run_id>/brief.json`
- Quality gates (CI enforces 100% coverage):
  - `poetry run ruff check . && poetry run mypy .`
  - `poetry run pytest --cov=src/trading_platform --cov-config=.coveragerc --cov-fail-under=100 -q`
  - `poetry run python tools/check_import_boundaries.py`

## Conventions and patterns (project-specific)
- Import boundaries: Cross-top imports must go via public APIs or `core`/`portfolio`. Only `src/trading_platform/cli.py`, `core/run.py`, `core/demo.py` may integrate across modules.
- Strategy vs. Risk separation: strategy files/configs must not contain risk keywords (see `tools/check_strategy_risk_separation.py`). Configure exits via REM, not in strategy rules.
- Signals contract: `Series[str]` of exactly `{'long','short','flat'}` and same length as OHLCV `DataFrame` with `open,high,low,close,volume`.
- `RunConfig` (pydantic) in `core/config.py` centralizes run settings (e.g., `initial_cash`, `position_size`, `blackout_utc`, `pm_limits`, `daily_loss_cap`, `counterfactual_mode`). `initialize_run`/`finalize_run` snapshot config and artifacts.
- Indicators SSOT: define and extend indicators via `strategy/indicators_registry.py`.
  Prefer `pandas-ta` primitives; avoid custom math unless explicitly needed.
  Align schemas/loaders with the registry.
- Schemas: strategy/RMM YAML must validate against JSON Schemas in
  `docs/schemas/*.json`; fail fast with clear errors.
- Testing: BDD features live under `tests/features/**`; `tests/test_core.py`
  aggregates scenarios. CI runs on Ubuntu with Python 3.10 and enforces 100%
  coverage (`.coveragerc`). Ruff line-length is 88; mypy targets Python 3.12 in
  config; keep code 3.10+ compatible.

## Strategy and risk configuration (examples)
- Strategy (YAML/JSON) compiled by `strategy/yaml_strategy.py`; rules use `any_of`/`all_of` with predicates `{condition,left,right}` (`is_above`, `is_below`, `cross_above`, `cross_below`). Example block:
  - long entry: `{ any_of: [ { condition: cross_above, left: {ref: ema_fast}, right: {ref: ema_slow} } ] }`
- Parameters and optional filters:
  - `parameters.slope_filter: true`, `parameters.slope_feature: ema_slow` gates entries by slope.
  - `ai_filter.enabled: true` can gate entries using `ai/inference_client.py` predictions if available.
- Risk & Exit Manager (REM): pass `rem_config` (e.g., `{"stop_loss": {"price_offset": 0.01}, "take_profit": {"price_offset": 0.02}}`) to `RiskExitManager` used in the backtester loop before strategy exits.
- Regime Market Manager (RMM): provide `rmm_config` to classify daily regimes, project per-bar `allowed_sides` and gate entry decisions; spans saved to `rmm_spans.json` for chart shading.

## Integration points and data
- Data loading: CLI supports `data_request` via `data.loader.load_from_catalog` using `config/data_catalog.yaml`; otherwise demo/toy data.
- Portfolio and costs: `PortfolioManager` applies fills/costs using `core/costs.py` cost model snapshot embedded in `RunConfig` and brief.
- Reporting: `reporting/brief.py` aggregates run meta, robustness summaries,
  parameter search, walk-forward, Monte Carlo, exposure curve, and
  skipped-trade counterfactuals. When adding new outputs, wire them through
  `core/run.finalize_run` → `reporting/brief.save_run_brief` and add tests.

Tips for agents
- Prefer adding new features via config or module-level APIs; avoid deep cross-imports (run boundary checker locally when in doubt).
- When extending CLI, wire new subcommands through `argparse` and keep artifacts under `runs/<user>/<run_id>` consistent with `finalize_run`.

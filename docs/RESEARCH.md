# Research Workflow Guide

This guide explains how to run systematic strategy research with the platform:
parameter search, walk‑forward optimize→test, and Monte Carlo resimulation.
It is strategy‑agnostic and works for any YAML strategy in the repo.

## Prerequisites
- Python env via Poetry with project deps installed (incl. `ta`).
- Data catalog configured if you use `data_request` (see `config/data_catalog.yaml`).
- Basic familiarity with the CLI: `python -m trading_platform.cli`.

## Quick Start (zero‑editing)
Generate a ready‑to‑run research config from a small JSON grid using the helper
tool. The output is a YAML file you can run immediately.

1) Create a grid file (example: `grid.json`):
   {
     "ema_fast_length": [8, 12, 16, 20],
     "ema_slow_length": [26, 50, 80, 100]
   }

2) Generate a config:
   python tools/make_research_config.py \
     --strategy config/strategy/ema_crossover.yaml \
     --symbol EUR_USD \
     --timeframe 1H \
     --start 2023-01-01 \
     --end 2023-03-01 \
     --grid-json grid.json \
     --out configs/research_ema.yaml

3) Run the research backtest:
   poetry run python -m trading_platform.cli run-backtest \
     --config configs/research_ema.yaml --user researcher

Artifacts are saved under `runs/<user>/<run_id>/` including `brief.json` and
`report.html`.

## What the generated config does
- Parameter search (full re‑runs): evaluates all grid candidates and records
  `parameter_search.results` and a `top` candidate in the brief.
- Walk‑forward optimize→test: optimizes on each train window (using the same
  grid) and evaluates out‑of‑sample on the next window; results in
  `walk_forward.splits` and `oos_total_pnl` summary.
- Monte Carlo resimulation: resamples bars per trial and re‑runs the full
  engine; reports distributions, tail risks, and exemplar paths in
  `monte_carlo`.

## Tuning the objective and penalties
In the config’s `parameter_search` block, set one of:
- `total_pnl` — maximize total PnL.
- `pnl_minus_dd` — maximize PnL minus `dd_penalty × MaxDD`.
- `pnl_dd_vol` — same as above minus `vol_penalty × PnL_std`.

Suggested starting values:
- `dd_penalty: 0.5`, `vol_penalty: 0.1` (adjust per strategy risk profile).

## Speeding up iteration
- Use `fast_mode.limit_bars: 10000` during exploration.
- Narrow grids after a coarse pass to reduce combinations.
- Disable `rmm_path` temporarily to see pure strategy behavior; re‑enable to
  validate filter value.

## Comparing runs
Generate HTML comparisons of recent runs:
  poetry run python -m trading_platform.cli compare --last 4 \
    --runs-dir runs --user researcher

This writes `compare_<runA>_vs_<runB>.html` files in CWD.

## Reading the brief
Key sections in `brief.json`:
- `overall_performance` — n_trades, total/mean/median PnL, win_rate.
- `equity_stats` — equity/drawdown curves, max_drawdown, duration.
- `parameter_search` — `top` and full `results` with scores.
- `walk_forward` — chosen params per split and OOS PnL aggregates.
- `monte_carlo` — distributions, `risk` (VaR/CVaR), `ruin_prob`, TUW, exemplars.
- `costs` — totals and breakdown; check sensitivity to cost assumptions.

## Risk & translation
- Strategy vs Risk separation is enforced:
  - Strategy: signal generation only.
  - REM: stop/TP/trailing exits (canonical values); see `config/rem/`.
  - EL/BT perform translation and enforcement consistently.

## Strategy‑agnostic usage
To reuse the flow with any strategy:
1) Point `--strategy` to your strategy YAML.
2) Provide a grid for that strategy’s parameter names (as defined under
   `strategy.parameters` and referenced via `${param}` in features/rules).
3) Adjust `walk_forward.window/step` to the strategy cadence.
4) Adjust REM and costs to realistic assumptions for the instrument.

## Monte Carlo configuration
Set under `monte_carlo`:
- `mode`: `bar_resimulation` (full resim) or `bar_bootstrap`.
- `trials`, `seed`.
- `cost_jitter`: `spread_jitter_pct`, `slippage_jitter_pct`,
  `per_trade_cost_jitter_pct`.
- `perturbation`: `mode: block|gaussian`, `block_len`, `std_pct`.

Interpretation guidelines:
- Prefer `cvar_95` and `ruin_prob` for tail risk.
- Check `time_under_water_mean` for path discomfort.

## Best practices
- Start coarse → narrow; always confirm with walk‑forward OOS.
- Use MC to gate top configs (tail risk and TUW) before promoting.
- Validate on multiple periods and a second symbol to reduce overfitting.
- Keep grids realistic; avoid giant cartesian products.

## Troubleshooting
- Schema validation errors when writing briefs: ensure your `brief.schema.json`
  covers new fields; the repo already enumerates MC/WF/PS fields.
- Missing indicators: update the registry at
  `src/trading_platform/strategy/indicators_registry.py` and add tests.
- YAML parse errors: if PyYAML is missing, provide JSON configs or install it.

## Automation ideas
- Batch multiple symbols/periods by generating configs programmatically with
  `make_research_config` and scripting CLI runs.
- Parallelize runs by sharding configs across processes or machines.

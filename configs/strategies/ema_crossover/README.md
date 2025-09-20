# EMA Crossover — Research Profile

This folder contains a self‑contained research run config and scripts for the
EMA crossover strategy. Use these as a template to create other strategy
profiles under `configs/strategies/<name>/`.

## Files
- research.yaml — Run config with parameter_search, walk_forward, monte_carlo.
- run_research.sh — Runs the research config and writes a brief + report.
- run_backtest.sh — Runs a single baseline backtest (no research features).

## Usage
- Make scripts executable once:
  chmod +x run_research.sh run_backtest.sh
- Run the full research job:
  ./run_research.sh
- Run a single baseline backtest:
  ./run_backtest.sh

Adjust dates, grid, and penalties in `research.yaml` as you iterate.

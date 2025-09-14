Trading Platform – Quickstart

Backtest → Brief → Report → Compare → Live (dry-run)

1) Backtest (demo)
   - `poetry run tp run-backtest --demo`
   - Outputs: `runs/<user>/<run_id>/brief.json`, `report.html`, `trades.csv`

2) Backtest (config)
   - `poetry run tp run-backtest --config docs/examples/backtest_config.json`
   - Minimal strategy runs on toy data and writes artifacts under `runs/...`.

3) Compare two runs (HTML)
   - Use reporting helpers directly or CLI (if enabled):
     - Python: `compare_briefs` + `render_comparison_html`
     - CLI: `poetry run tp compare A/brief.json B/brief.json --out cmp.html`

4) Live (stub, dry-run)
   - `poetry run tp run-live --dry-run`
   - For config path: `poetry run tp run-live --config docs/examples/live_config.json`
   - Uses OandaStubAdapter; enforces blackout and position caps.

Notes
- Keep line length ≤88 in code/tests. Run `ruff`, `mypy`, `pytest -q`.
- See `docs/examples/` for minimal JSON configs.

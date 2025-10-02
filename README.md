Trading Platform – Quickstart

![Test Coverage](https://img.shields.io/badge/coverage-91.89%25-brightgreen)
![Test Pass Rate](https://img.shields.io/badge/tests-93.3%25%20passing-green)
![Total Tests](https://img.shields.io/badge/tests-1183-blue)
![Requirements Coverage](https://img.shields.io/badge/requirements-75%20tracked-blue)

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

## Testing & Quality Metrics

- **Code Coverage**: 91.89% (target: 80%+) ✅
- **Test Pass Rate**: 93.3% (1,104 / 1,183 tests)
- **Requirements Tracked**: 75 unique requirements
- **Requirements Coverage**: 57.1% with traceability comments
- **Test Execution Time**: 40.33 seconds

Run tests: `poetry run pytest tests/`
Generate coverage report: `poetry run pytest --cov=trading_platform --cov-report=html`

See [REQUIREMENTS_CHECK_REPORT_FINAL.md](REQUIREMENTS_CHECK_REPORT_FINAL.md) for detailed coverage analysis.

Notes
- Keep line length ≤88 in code/tests. Run `ruff`, `mypy`, `pytest -q`.
- See `docs/examples/` for minimal JSON configs.
- See [docs/testing_guide.md](docs/testing_guide.md) for test writing guidelines.

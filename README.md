# Trading Platform (MVP)
Phase 1.1: project skeleton + hello_run
# Trading Platform

This repository contains the source code for a world-class, AI-powered, instrument-agnostic trading platform.

## Quickstart

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1.  **Install dependencies:**
    ```bash
    poetry install
    ```
2.  **Run the initial entrypoint:**
```bash
python -m trading_platform.core.run
poetry run python -m trading_platform.core.run
```
This creates `runs/{run_id}/meta.json` and writes a log line.

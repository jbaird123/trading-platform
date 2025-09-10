# Trading Platform (MVP)
This repository contains the Minimum Viable Product (MVP) for a modular trading platform.

## Setup

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1.  **Install dependencies:**
    ```bash
    poetry install
    ```
    This will create a virtual environment and install all required packages.

## Quickstart
1.  **Run the application:**
    ```bash
    poetry run python -m trading_platform.core.run
    ```
    This creates a new run directory `runs/{run_id}/config.json` and writes a log line.

2.  **Run tests:**
    ```bash
    poetry run pytest
    ```
    This will execute the test suite to verify the core functionality.

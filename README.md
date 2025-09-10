# Trading Platform (MVP)
This repository contains the Minimum Viable Product (MVP) for a modular trading platform.

## Setup

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1.  **Install Poetry:**
    If you do not have Poetry installed, you can install it by following the instructions on the [official website](https://python-poetry.org/docs/#installation). The recommended method is:
    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```
    After installation, you may need to restart your terminal or configure your shell's `PATH` for the `poetry` command to be available.

2.  **Install Project Dependencies:**
    Once Poetry is installed, navigate to the project root and run:
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

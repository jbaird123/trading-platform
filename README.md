# Modular Trading & Backtesting Platform

![Test Coverage](https://img.shields.io/badge/coverage-91.89%25-brightgreen)
![Test Pass Rate](https://img.shields.io/badge/tests-100%25%20passing-green)
![Total Tests](https://img.shields.io/badge/tests-1358-blue)
![Requirements Coverage](https://img.shields.io/badge/requirements-75%20tracked-blue)

This is a high-performance, event-driven backtesting and trading platform built with a focus on modularity, testability, and professional-grade software architecture. It allows for the rigorous testing of complex trading strategies, from signal generation to risk management and portfolio analysis.

Architected and developed by a single engineer leveraging AI-augmented development techniques, this project demonstrates the power of combining human architectural expertise with AI-driven code generation to rapidly build complex, high-quality software.

## Core Features

- **Event-Driven Backtester**: Simulates trading strategies with high fidelity, processing market data minute-by-minute to avoid lookahead bias.
- **Declarative Strategy Engine**: Define complex trading logic in simple, readable YAML files. Strategies are completely decoupled from risk management.
- **Pluggable Risk & Exit Management (REM)**: Define exit logic (stop-losses, take-profits) separately from entry signals, allowing for mix-and-match testing of risk models.
- **Regime-Based Market Analysis (RMM)**: Classify market conditions (e.g., "trending," "ranging") and dynamically enable or disable strategies based on the prevailing regime.
- **Comprehensive Reporting**: Automatically generates detailed HTML reports, `brief.json` summaries, and trade logs for each backtest.
- **AI/ML Research Lab**: A dedicated module for experimenting with machine learning models for signal generation and market analysis.

## Architecture

The platform is built on a foundation of clean architecture and **separation of concerns**. The diagram below illustrates the high-level system architecture and the flow of information between components. A more detailed breakdown is available in the [System Architecture documentation](docs/architecture.md).

```mermaid
graph TD
    subgraph "Input"
        Config[Config File (.yaml, .json)]
    end

    subgraph "Orchestration"
        CLI(CLI)
        Backtester[Event-Driven Backtester]
    end

    subgraph "Data Processing"
        DataSource[Data Source]
    end

    subgraph "Decision Logic"
        RMM[Regime Market Manager]
        Strategy[Strategy Engine]
        REM[Risk & Exit Manager]
    end

    subgraph "State Management"
        Portfolio[Portfolio Manager]
        Execution[Execution Handler]
    end

    subgraph "Output"
        Reports[HTML Reports & JSON data]
    end

    CLI -- Reads --> Config
    CLI -- Initiates --> Backtester
    DataSource -- Market Data --> Backtester

    Backtester -- Tick Event --> RMM
    RMM -- Market Regime --> Strategy
    Backtester -- Tick Event --> Strategy
    Strategy -- Entry Signal --> Backtester

    Backtester -- Open Trade --> Execution
    Execution -- Fill Event --> Portfolio
    Backtester -- Tick Event --> REM
    REM -- Manages open trade --> Portfolio
    REM -- Exit Signal --> Backtester

    Backtester -- Close Trade --> Execution

    Backtester -- Generates --> Reports
```

The most critical design principle is the strict separation of the **Strategy Engine** from the **Risk & Exit Manager (REM)**. This decoupling allows for immense flexibility, where any strategy can be tested against any risk management model.

## Technology Stack

- **Language**: Python (3.12+)
- **Dependency Management**: Poetry
- **Core Libraries**: pandas, NumPy, Pyarrow
- **API & Web**: FastAPI, Uvicorn
- **Data Validation**: Pydantic
- **ML & Research**: scikit-learn, LightGBM, SHAP, MLflow
- **Testing**: Pytest, pytest-bdd, Coverage.py
- **Linting & Formatting**: Ruff, MyPy

## Installation

#### Prerequisites
- Python (version 3.12 or higher)
- [Poetry](https://python-poetry.org/docs/#installation)

#### Steps
1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd trading-platform
    ```
3.  **Install dependencies:**
    ```bash
    poetry install
    ```
4.  **Verify the installation by running the test suite:**
    ```bash
    poetry run pytest
    ```
    All tests should pass, confirming the environment is set up correctly.

## Quickstart

1.  **Run a demo backtest:**
    ```bash
    poetry run tp run-backtest --demo
    ```
    This will run a pre-configured backtest and output the results to the `runs/` directory.

2.  **Run a backtest from a config file:**
    ```bash
    poetry run tp run-backtest --config docs/examples/backtest_config.json
    ```

3.  **Compare two backtest results:**
    ```bash
    poetry run tp compare path/to/run_A/brief.json path/to/run_B/brief.json
    ```

## Development & Quality

- **Run tests:**
  ```bash
  poetry run pytest
  ```
- **Run linter and type checker:**
  ```bash
  poetry run ruff check . && poetry run mypy .
  ```
- **Generate coverage report:**
  ```bash
  poetry run pytest --cov=trading_platform --cov-report=html
  ```

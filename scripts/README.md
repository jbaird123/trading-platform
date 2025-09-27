# Trading Platform Scripts

This directory contains convenience scripts for common development and operational tasks.

## Available Scripts

### 🔄 Data Synchronization

#### `sync-data.sh`
General data synchronization script that accepts any sync parameters.

**Usage:**
```bash
# Sync specific symbol
./scripts/sync-data.sh --symbol EUR/USD --data-root ./data

# Sync all instruments
./scripts/sync-data.sh --all --data-root ./data

# Get help
./scripts/sync-data.sh --help
```

#### `sync-all.sh`
Quick script to sync all instruments using the default `./data` directory.

**Usage:**
```bash
./scripts/sync-all.sh
```

This script will:
- Create `./data/full/` and `./data/incremental/` directories if they don't exist
- Sync all instruments defined in the platform
- Use the project's `./data` directory as the data root

### 🚀 Strategy Improvement

#### `run-improvement-cycle.sh`
Automates one full cycle of the strategy improvement plan. It runs a full backtest with all analyses (parameter search, WFE, Monte Carlo) and then generates both quantitative and qualitative AI diagnostic reports.

**Usage:**
```bash
# Run a full improvement cycle on a strategy config
./scripts/run-improvement-cycle.sh configs/strategies/ema_crossover/backtest.yaml
```
This script will:
1.  Run the backtest with all analyses enabled in the config file.
2.  Generate a quantitative `ai_diagnostic_report.json`.
3.  Generate a qualitative `ai_qualitative_report.md` (using an external LLM).
4.  Print the locations of all reports and guide you on the next steps for iterative improvement.

### 🧪 Development & Testing

#### `dev-test.sh`
Runs the complete development test suite including tests, linting, and type checking.

**Usage:**
```bash
./scripts/dev-test.sh
```

This script runs:
1. `poetry run pytest -q` - Full test suite
2. `poetry run ruff check .` - Code linting
3. `poetry run mypy .` - Type checking

#### `run-backtest.sh`
Runs the platform's demo backtest for quick validation.

**Usage:**
```bash
./scripts/run-backtest.sh
```

## Making Scripts Executable

After cloning the repository, make the scripts executable:

```bash
chmod +x scripts/*.sh
```

## Script Conventions

- All scripts change to the project root directory before executing
- Scripts use `set -e` to exit on any error
- Scripts provide clear output with emoji indicators
- Scripts are designed to be run from any location in the project

## Adding New Scripts

When adding new scripts:

1. Use the same header format with description and usage
2. Include `set -e` for error handling
3. Navigate to project root using the established pattern
4. Add documentation to this README
5. Make the script executable with `chmod +x`

# Testing Guide

## Table of Contents
1. [Overview](#overview)
2. [Test Organization](#test-organization)
3. [Requirement Traceability](#requirement-traceability)
4. [Writing Tests](#writing-tests)
5. [Running Tests](#running-tests)
6. [Best Practices](#best-practices)

## Overview

This project maintains comprehensive test coverage with explicit traceability to requirements. Every test should validate a specific requirement and be clearly documented.

## Test Organization

Tests are organized by module:

```
tests/
├── data/               # Data Handler tests (DH-*)
├── strategy/           # Strategy Engine tests (SE-*)
├── regime_market_manager/  # RMM tests (RMM-*)
├── portfolio/          # Portfolio Manager tests (PM-*)
├── risk_manager/       # Risk & Exit Manager tests (REM-*)
├── backtester/         # Backtester tests (BT-*)
├── execution/          # Execution Layer tests (EL-*)
├── ai/                 # AI Lab tests (AI-*)
├── reporting/          # Reporting & Validation tests (RV-*, JSON-*)
├── core/               # System-Wide tests (SYS-*)
└── performance/        # Performance benchmarks (SYS-1.9.*)
```

## Requirement Traceability

### Best Practices

Every test file MUST include a traceability comment in its module docstring:

```python
"""Tests for portfolio manager state management.

# Validates: [PM-5.1], [PM-5.3], [PM-5.4]
"""
```

### Individual Test Traceability

Individual tests should also include validation comments:

```python
def test_portfolio_initialization():
    """Verify the portfolio initializes with correct default values.

    Validates: [PM-5.1], [PM-5.2]
    """
    portfolio = PortfolioManager(initial_cash=50000)
    assert portfolio.initial_cash == 50000
```

### Traceability Comment Format

**Module Level:**
```python
"""<Module description>

# Validates: [REQ-ID-1], [REQ-ID-2], [REQ-ID-3]
"""
```

**Test Level:**
```python
def test_something():
    """<Test description>

    Validates: [REQ-ID]
    """
```

### Requirement ID Conventions

- **SYS-X.Y.Z** - System-wide requirements
- **DH-X.Y** - Data Handler requirements
- **SE-X.Y** - Strategy Engine requirements
- **RMM-X.Y** - Regime Market Manager requirements
- **PM-X.Y.Z** - Portfolio Manager requirements
- **REM-X.Y** - Risk & Exit Manager requirements
- **BT-X.Y** - Backtester requirements
- **EL-X.Y** - Execution Layer requirements
- **AI-X.Y.Z** - AI Lab requirements
- **RV-X.Y** - Reporting & Validation requirements
- **JSON-X.Y** - JSON Brief Schema requirements

## Writing Tests

### Test Naming Convention

Use descriptive names that indicate what is being tested:

```python
def test_pm_5_8_1_tracks_bar_index_when_entry_command_received():
    """Validates: [PM-5.8.1]"""
    # Test implementation
```

### Test Structure

Follow the Arrange-Act-Assert pattern:

```python
def test_portfolio_processes_buy_order():
    """Validates: [PM-5.4]"""
    # Arrange
    portfolio = PortfolioManager(initial_cash=100000)
    entry_bar = pd.Series({"close": 1.1000}, name=datetime(2024, 1, 1))

    # Act
    portfolio.create_new_position("EURUSD", "long", 1.1000, 10000, datetime(2024, 1, 1))

    # Assert
    assert portfolio._open_position is not None
    assert portfolio._open_position.side == "long"
```

### Mock Data

Use realistic mock data:

```python
def create_mock_data(periods=100):
    """Create mock OHLCV data for testing."""
    timestamps = pd.date_range("2024-01-01", periods=periods, freq="1h")
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": [1.1000 + i * 0.0001 for i in range(periods)],
        "high": [1.1010 + i * 0.0001 for i in range(periods)],
        "low": [1.0990 + i * 0.0001 for i in range(periods)],
        "close": [1.1005 + i * 0.0001 for i in range(periods)],
        "volume": [1000 + i for i in range(periods)]
    })
```

### Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
def mock_portfolio():
    """Create a mock portfolio for testing."""
    return PortfolioManager(initial_cash=100000)

def test_with_fixture(mock_portfolio):
    """Validates: [PM-5.1]"""
    assert mock_portfolio.cash == 100000
```

## Running Tests

### Run All Tests

```bash
poetry run pytest
```

### Run Specific Module

```bash
poetry run pytest tests/portfolio/
```

### Run with Coverage

```bash
poetry run pytest --cov=trading_platform --cov-report=html
```

### Run Tests for Specific Requirement

```bash
poetry run pytest -k "pm_5_8"  # All PM-5.8.* tests
```

### Run Performance Tests

```bash
poetry run pytest tests/performance/ -v
```

## Best Practices

### 1. Test Independence

Each test should be independent and not rely on other tests:

```python
# Good
def test_portfolio_buy():
    portfolio = PortfolioManager(initial_cash=100000)
    # Test buy logic

def test_portfolio_sell():
    portfolio = PortfolioManager(initial_cash=100000)
    # Test sell logic

# Bad - depends on test_portfolio_buy running first
portfolio = None
def test_portfolio_buy():
    global portfolio
    portfolio = PortfolioManager(initial_cash=100000)

def test_portfolio_sell():
    # Uses global portfolio from previous test
```

### 2. Explicit Assertions

Make assertions explicit and clear:

```python
# Good
assert portfolio.cash == 90000, f"Expected cash=90000, got {portfolio.cash}"
assert len(portfolio.trades) == 1
assert portfolio.trades[0].pnl > 0

# Bad
assert portfolio.cash  # What value should this be?
```

### 3. Test Edge Cases

Always test boundary conditions:

```python
def test_portfolio_handles_zero_cash():
    """Validates: [PM-5.3]"""
    portfolio = PortfolioManager(initial_cash=0)
    # Test behavior with zero cash

def test_portfolio_handles_negative_pnl():
    """Validates: [PM-5.7]"""
    # Test losing trades
```

### 4. Use Descriptive Error Messages

```python
assert result == expected, \
    f"Expected {expected}, got {result}. Context: {context}"
```

### 5. Mock External Dependencies

Always mock external API calls, file I/O, and network requests:

```python
from unittest.mock import Mock, patch

def test_api_call():
    """Validates: [EL-8.2]"""
    mock_api = Mock()
    mock_api.get_account.return_value = {"balance": 10000}

    result = execute_trade(mock_api)
    assert result is not None
```

### 6. Performance Tests

Mark performance-critical tests:

```python
@pytest.mark.performance
def test_indicator_computation_speed():
    """Validates: [SYS-1.9.1]"""
    # Benchmark indicator computation
```

### 7. Parameterized Tests

Use `pytest.mark.parametrize` for multiple scenarios:

```python
@pytest.mark.parametrize("entry_window_bars,expected_behavior", [
    (0, "exact_bar_only"),
    (3, "three_bar_window"),
    (-1, "infinite_window")
])
def test_entry_window_policies(entry_window_bars, expected_behavior):
    """Validates: [PM-5.8.3]"""
    # Test different window policies
```

### 8. Skip Tests Conditionally

```python
@pytest.mark.skipif(not psutil, reason="psutil required for memory tests")
def test_memory_usage():
    """Validates: [SYS-1.9.2]"""
    # Memory profiling test
```

## Continuous Integration

Tests run automatically on:
- Every push to `dev` branch
- Every pull request
- Nightly full test suite

### CI Requirements

- All tests must pass
- Code coverage must not decrease
- Performance benchmarks must not regress by >10%

## Troubleshooting

### Test Failures

1. Read the full error message
2. Check if test data is correct
3. Verify requirement hasn't changed
4. Run test in isolation: `pytest tests/path/to/test.py::test_name -vv`

### Slow Tests

1. Use `--durations=10` to find slowest tests
2. Consider mocking expensive operations
3. Use smaller datasets for unit tests
4. Move slow tests to integration test suite

## Golden Validation Testing

### Overview

Golden validation tests compare our platform's output against TradingView exports to ensure correctness. These are integration tests that validate the entire calculation pipeline.

### Critical: TradingView Export Date Range

**⚠️ ALWAYS set export start date EARLIER than validation start date!**

When exporting trade data from TradingView for golden validation:

1. **Validation period**: The actual date range you want to test (e.g., 2023-01-01 to 2024-12-31)
2. **Export start date**: At least 1 MONTH BEFORE the validation start (e.g., 2022-12-01)
3. **Why this matters**:
   - Indicators need historical data to "warm up" before producing accurate values
   - TradingView may filter out trades that occur near the export start date
   - Without warmup data, early trades may be missing or have different values
   - **100 bars is NOT enough** - empirical testing shows 1 month is required for accurate matching

**Example:**
```
Validation range:  2023-01-01 to 2024-12-31
Export start:      2022-12-01 (1 month buffer - REQUIRED)
Export end:        2024-12-31
```

**Recommended buffer sizes (minimum):**
- Hourly data: 1 month (~720 bars) - 100 bars is insufficient
- Daily data: 6 months (~130 bars minimum)
- 4-hour data: 1 month (~180 bars minimum)

**Note**: The old "100 bars" guidance was found to be insufficient. Golden validation testing with EMA crossover strategies showed that using exactly 1 month of warmup data (2022-12-01 for a 2023-01-01 validation start) produces perfect matching with TradingView, while 100 bars led to discrepancies.

### How Filtering Works

The test suite automatically filters trades to the validation range:

1. Export includes warmup period trades (before validation start)
2. `tradingview_trades` fixture filters to only include trades where `entry_time >= validation_start`
3. Platform backtest runs on extended data (with warmup)
4. `load_platform_trades()` filters platform trades to validation range
5. Both datasets now have matching trade counts for comparison

See: `tests/validation/conftest.py::tradingview_trades()` for implementation details.

### Documentation Locations

When setting up golden validation for a new strategy, document the export requirements in:

1. **Strategy README**: `configs/golden_strategies/{strategy_name}/README.md`
2. **This guide**: You're reading it now
3. **Code comments**: In `tests/validation/conftest.py`

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [REQUIREMENTS.md](../REQUIREMENTS.md) - Full requirements list
- [requirement_to_test_map.md](./requirement_to_test_map.md) - Requirement → Test mapping
- [Golden Validation Setup](./code_tasks/setup_tradingview_golden_validation.md) - Detailed golden validation guide

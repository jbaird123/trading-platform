# Contributing to Trading Platform

Thank you for your interest in contributing to the Trading Platform! This document provides guidelines for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Exception Handling Guidelines](#exception-handling-guidelines)
- [Testing](#testing)
- [Code Style](#code-style)

## Code of Conduct

Be respectful, professional, and constructive in all interactions.

## Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/trading-platform.git
   cd trading-platform
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Run tests**
   ```bash
   poetry run pytest
   ```

## Development Workflow

1. Create a feature branch from `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and write tests

3. Run tests and linting:
   ```bash
   poetry run pytest
   poetry run ruff check src/
   poetry run mypy src/ tests/
   ```

4. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: description of your feature"
   ```

5. Push and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

## Exception Handling Guidelines

The Trading Platform follows a **fail-fast by default** principle. Please review the [Exception Handling Policy](docs/coding_standards/exception_handling_policy.md) before writing code that catches exceptions.

### Golden Rule

**When in doubt, FAIL LOUDLY rather than log/warn.**

Warnings and logging should only happen when we know with 100% certainty that there is no adverse effect. If there is any doubt, then the correct action is to fail loudly.

### Quick Reference

#### ✅ CORRECT: Fail Fast (Default)
```python
# Data loading - critical path
def load_data(path: Path) -> pd.DataFrame:
    # No try/except - let errors propagate
    return pd.read_csv(path)

# User-requested analysis
def run_monte_carlo(trades: list[Trade], trials: int) -> dict:
    # No try/except - user needs to know if this fails
    return monte_carlo_summary(trades, trials=trials)
```

#### ✅ CORRECT: Logged Degradation (When Safe)
```python
# Optional chart generation
def save_chart(path: Path, data: dict) -> None:
    try:
        chart_html = generate_chart(data)
        path.write_text(chart_html)
    except Exception as e:
        # Safe to continue: chart is optional visualization
        # brief.json contains all data
        logger.debug(f"Failed to generate chart: {e}")
```

#### ❌ WRONG: Silent Failure
```python
# WRONG - silently ignores data loading errors
def load_data(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()  # ❌ Returns empty, hides error
```

### The Three-Question Test

Before catching an exception, ask:

1. **Can the system produce correct results without this feature?**
2. **Is there any scenario where hiding this error causes incorrect behavior?**
3. **Would a user prefer a clear error over silent degradation?**

If #1 is uncertain, #2 is yes, or #3 is yes → **FAIL FAST**

### Common Patterns

**Optional Features** (charts, analytics, metadata):
- Use `try/except` with `logger.debug()` or `logger.warning()`
- Return empty dict `{}` or `None`
- Document why it's safe in a comment

**Critical Paths** (data loading, calculations, user requests):
- No `try/except` - let exceptions propagate
- User sees clear error message
- System fails fast and doesn't hide problems

**File I/O for Convenience** (CSV exports, cache files):
- Use `try/except` with `logger.warning()`
- Document that data exists elsewhere (e.g., in brief.json)

### Examples

See [Exception Handling Policy](docs/coding_standards/exception_handling_policy.md) for comprehensive examples and decision trees.

## Testing

- Write tests for both success and failure paths
- Test that critical paths fail fast with clear errors
- Test that optional features degrade gracefully

```python
# Test fail-fast behavior
def test_invalid_data_raises_error():
    with pytest.raises(ValueError, match="Invalid data"):
        process_data(invalid_input)

# Test graceful degradation
def test_chart_failure_logs_warning(caplog):
    save_chart(path, malformed_data)
    assert "Failed to generate chart" in caplog.text
```

## Code Style

- Follow PEP 8
- Use type hints
- Run `ruff` and `mypy` before committing
- Maximum line length: 88 characters
- Use docstrings for public functions

## Pre-commit Hooks

Pre-commit hooks automatically run:
- Trailing whitespace removal
- EOF fixer
- YAML validation
- Ruff linting and formatting
- Custom checks for imports and strategy logic

Install pre-commit hooks:
```bash
poetry run pre-commit install
```

## Questions?

If you have questions, please:
1. Check the documentation in `docs/`
2. Review existing code and tests
3. Open an issue for clarification

Thank you for contributing!

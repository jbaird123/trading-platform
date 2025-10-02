# Contributing to Trading Platform

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Testing Requirements](#testing-requirements)
5. [Requirement Validation](#requirement-validation)
6. [Code Style](#code-style)
7. [Pull Request Process](#pull-request-process)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the project
- Show empathy towards other contributors

## Getting Started

### Prerequisites

- Python 3.10+
- Poetry for dependency management
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/trading-platform.git
cd trading-platform

# Install dependencies
poetry install

# Run tests to verify setup
poetry run pytest
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clean, readable code
- Follow existing code patterns
- Add docstrings to all functions/classes
- Update documentation as needed

### 3. Write Tests

**All new code MUST include tests.** See [Testing Requirements](#testing-requirements).

### 4. Run Tests Locally

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=trading_platform --cov-report=html

# Check for regressions
poetry run pytest tests/performance/
```

### 5. Commit Changes

Follow conventional commit format:

```bash
git commit -m "feat: add new feature"
git commit -m "fix: resolve bug in portfolio manager"
git commit -m "docs: update testing guide"
git commit -m "test: add tests for RMM hysteresis"
```

Commit types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or modifying tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Maintenance tasks

## Testing Requirements

### Requirement Traceability

**CRITICAL**: Every test MUST be traceable to a specific requirement.

#### Module-Level Traceability

Add validation comments to test file docstrings:

```python
"""Tests for portfolio manager state management.

# Validates: [PM-5.1], [PM-5.3], [PM-5.4]
"""
```

#### Test-Level Traceability

Add validation comments to individual tests:

```python
def test_portfolio_initialization():
    """Verify the portfolio initializes with correct default values.

    Validates: [PM-5.1], [PM-5.2]
    """
    portfolio = PortfolioManager(initial_cash=50000)
    assert portfolio.initial_cash == 50000
```

### Test Coverage Requirements

- Minimum 80% code coverage for new code
- 100% coverage for critical paths (order execution, risk management)
- All edge cases must be tested
- Performance-critical code must have benchmarks

### Test Organization

Place tests in the appropriate directory:

```
tests/
├── data/               # DH-* requirements
├── strategy/           # SE-* requirements
├── regime_market_manager/  # RMM-* requirements
├── portfolio/          # PM-* requirements
├── risk_manager/       # REM-* requirements
├── backtester/         # BT-* requirements
├── execution/          # EL-* requirements
├── ai/                 # AI-* requirements
├── reporting/          # RV-*, JSON-* requirements
└── core/               # SYS-* requirements
```

## Requirement Validation

### Adding New Requirements

1. Document requirement in `REQUIREMENTS.md`
2. Assign a unique requirement ID (e.g., `PM-5.9`)
3. Create tests that validate the requirement
4. Add `# Validates: [REQ-ID]` comments
5. Update requirement-to-test mapping:
   ```bash
   python3 scripts/generate_requirement_test_map.py
   ```

### Modifying Existing Requirements

1. Update requirement documentation
2. Update or add tests as needed
3. Ensure all affected tests still pass
4. Update traceability comments
5. Regenerate requirement-to-test mapping

### Requirement ID Conventions

- **SYS-X.Y.Z**: System-wide requirements
- **DH-X.Y**: Data Handler requirements
- **SE-X.Y**: Strategy Engine requirements
- **RMM-X.Y**: Regime Market Manager requirements
- **PM-X.Y.Z**: Portfolio Manager requirements
- **REM-X.Y**: Risk & Exit Manager requirements
- **BT-X.Y**: Backtester requirements
- **EL-X.Y**: Execution Layer requirements
- **AI-X.Y.Z**: AI Lab requirements
- **RV-X.Y**: Reporting & Validation requirements
- **JSON-X.Y**: JSON Brief Schema requirements

### Checking Requirement Coverage

```bash
# Generate requirement-to-test mapping
python3 scripts/generate_requirement_test_map.py

# View coverage report
open docs/requirement_to_test_map.md
```

## Code Style

### Python Style Guide

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use descriptive variable names

### Example:

```python
def calculate_portfolio_value(
    positions: list[Position],
    current_prices: dict[str, float]
) -> float:
    """Calculate total portfolio value based on current prices.

    Args:
        positions: List of open positions
        current_prices: Dictionary mapping symbols to current prices

    Returns:
        Total portfolio value in base currency

    Validates: [PM-5.3]
    """
    total_value = 0.0

    for position in positions:
        current_price = current_prices.get(position.symbol, position.entry_price)
        position_value = position.size * current_price
        total_value += position_value

    return total_value
```

### Docstring Format

Use Google-style docstrings:

```python
def function_name(arg1: int, arg2: str) -> bool:
    """Brief description of function.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When and why this is raised

    Validates: [REQ-ID]
    """
```

### Formatting

Use `black` for code formatting:

```bash
poetry run black .
```

Use `isort` for import sorting:

```bash
poetry run isort .
```

## Pull Request Process

### Before Submitting

1. ✅ All tests pass locally
2. ✅ New tests added with requirement traceability
3. ✅ Code coverage has not decreased
4. ✅ Documentation updated
5. ✅ Requirement-to-test mapping regenerated
6. ✅ Code formatted with `black` and `isort`
7. ✅ Type hints added to new functions

### PR Description Template

```markdown
## Description
Brief description of changes

## Related Requirements
- [PM-5.8.1] Track bar index when entry command received
- [PM-5.8.2] Prevent duplicate entries

## Changes Made
- Added entry window tracking to PortfolioManager
- Created comprehensive tests for entry window management
- Updated documentation

## Testing
- Added 14 new tests in `tests/portfolio/test_entry_window_management.py`
- All tests pass (47/47)
- Coverage increased from 82% to 85%

## Checklist
- [x] Tests added with requirement traceability
- [x] Documentation updated
- [x] All tests pass
- [x] Code formatted
- [x] Requirement mapping regenerated
```

### Review Process

1. Automated checks must pass (CI/CD)
2. At least one code review required
3. All comments must be addressed
4. Maintainer approval required for merge

### After Merge

- Delete feature branch
- Update local main/dev branch
- Celebrate! 🎉

## Additional Resources

- [Testing Guide](docs/testing_guide.md)
- [Requirements](REQUIREMENTS.md)
- [Requirement-to-Test Mapping](docs/requirement_to_test_map.md)
- [Architecture Overview](docs/architecture.md)

## Questions?

Open an issue or reach out to maintainers.

Thank you for contributing! 🚀

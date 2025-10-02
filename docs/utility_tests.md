# Utility and Infrastructure Tests

This document lists tests that serve utility or infrastructure purposes rather than validating specific requirements.

## Core Utilities

### [tests/core/test_utils.py](../tests/core/test_utils.py)
- Symbol normalization helpers
- Utility function tests
- **Validates**: [SYS-1.2.4], [SYS-1.3.5]

## Strategy Base Classes

### [tests/strategy/test_base_strategy.py](../tests/strategy/test_base_strategy.py)
- Base strategy interface tests
- Abstract class validation
- **Validates**: [SE-3.2]

## Fixture and Configuration Tests

### [tests/conftest.py](../tests/conftest.py)
- pytest fixtures
- Test configuration
- Shared test setup

## BDD Step Definitions

Located in `tests/step_defs/`, these provide reusable step implementations for Gherkin scenarios:

- `backtester/test_signal_steps.py` - Signal generation steps
- `data_handler/test_data_schema_steps.py` - Data schema validation steps
- `data_handler/test_data_steps.py` - Data loading steps
- `regime_market_manager/test_classification_steps.py` - Classification steps
- `regime_market_manager/test_market_regime_classification_steps.py` - Market regime steps
- `strategy_engine/test_signal_generation_steps.py` - Strategy signal steps
- `strategy_engine/test_strategy_steps.py` - Strategy execution steps

## Notes

- Utility tests don't need to map to specific requirements
- They support the test infrastructure itself
- Should still follow coding standards and be well-documented
- May be excluded from requirements coverage calculations

# Validates: [SYS-1.10.2]
from __future__ import annotations

from pytest_bdd import scenarios

# Load all BDD scenarios from the .feature files
scenarios(
    "features/backtester",
    "features/data_handler",
    "features/portfolio",
    "features/regime_market_manager",
    "features/strategy_engine",
)

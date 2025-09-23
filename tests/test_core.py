# Validates: [SYS-1.10.2]
from __future__ import annotations

from pytest_bdd import scenarios

# Ensure step definitions are imported so pytest-bdd can register them.
# These imports are intentionally unused; importing registers step functions.
from tests.step_defs.backtester import (  # noqa: F401
    test_core_backtest_steps,
    test_risk_management_steps,
    test_signal_steps,
)
from tests.step_defs.data_handler import (  # noqa: F401
    test_data_schema_steps,
    test_data_steps,
)
from tests.step_defs.regime_market_manager import (  # noqa: F401
    test_classification_steps,
    test_market_regime_classification_steps,
)
from tests.step_defs.strategy_engine import (  # noqa: F401
    test_signal_generation_steps,
    test_strategy_steps,
)

# Load all BDD scenarios from the .feature files
scenarios(
    "features/backtester",
    "features/data_handler",
    "features/regime_market_manager",
    "features/strategy_engine",
)

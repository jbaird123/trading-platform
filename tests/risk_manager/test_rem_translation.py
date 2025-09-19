# Validates: [SYS-1.3.3]
from datetime import datetime

import pandas as pd
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.core import RiskExitManager


def test_rem_translates_pips_rule_for_long_position():
    """
    Tests that the REM correctly translates a 'pips' stop-loss rule into a
    canonical price level for a long position.
    """
    # 1. Setup
    rem_config = {"stop_loss": {"pips": 50}}
    instrument = {"pip_location": 0.0001}
    rem = RiskExitManager(config=rem_config, instrument=instrument)

    position = Position(
        symbol="EUR_USD",
        side="long",
        entry_price=1.20000,
        size=10000,
        entry_time=datetime.utcnow(),
    )

    # Pip size for EUR_USD is 0.0001. 50 pips = 0.0050
    expected_stop_price = 1.20000 - 0.0050  # 1.19500

    # 2. Create a bar where the low hits the stop price exactly
    bar_data = {
        "open": 1.1980,
        "high": 1.1990,
        "low": expected_stop_price,
        "close": 1.1960,
    }
    current_bar = pd.Series(bar_data, name=datetime.utcnow())

    # 3. Action
    exit_details = rem.check_exits(position, current_bar)

    # 4. Assert
    assert exit_details is not None
    assert exit_details["reason"] == "stop-loss"
    assert exit_details["exit_price"] == expected_stop_price


def test_rem_translates_pips_rule_for_short_position():
    """
    Tests that the REM correctly translates a 'pips' stop-loss rule into a
    canonical price level for a short position.
    """
    # 1. Setup
    rem_config = {"stop_loss": {"pips": 50}}
    instrument = {"pip_location": 0.01}  # For JPY pair
    rem = RiskExitManager(config=rem_config, instrument=instrument)

    position = Position(
        symbol="USD_JPY",
        side="short",
        entry_price=110.00,
        size=10000,
        entry_time=datetime.utcnow(),
    )

    # Pip size for USD_JPY is 0.01. 50 pips = 0.50
    expected_stop_price = 110.00 + 0.50  # 110.50

    # 2. Create a bar where the high hits the stop price exactly
    bar_data = {
        "open": 110.20,
        "high": expected_stop_price,
        "low": 110.10,
        "close": 110.40,
    }
    current_bar = pd.Series(bar_data, name=datetime.utcnow())

    # 3. Action
    exit_details = rem.check_exits(position, current_bar)

    # 4. Assert
    assert exit_details is not None
    assert exit_details["reason"] == "stop-loss"
    assert exit_details["exit_price"] == expected_stop_price

"""Risk & Exit Manager tests.

# Validates: [REM-6.1], [REM-6.2], [REM-6.3]
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
import yaml
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.rem import RiskExitManager

# Validates: [REM-6.1], [REM-6.2], [REM-6.3], [REM-6.4]


@pytest.fixture(scope="module")
def rem_config_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Creates a temporary REM config file for testing."""
    config = {
        "name": "Test REM Config",
        "stop_loss": {"pips": 50},
        "take_profit": {"price_offset": 0.0060},
    }
    path: Path = tmp_path_factory.mktemp("config") / "rem.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


def test_rem_config_loading(rem_config_path: Path):
    """Tests that the REM can be instantiated and loads a config."""
    rem = RiskExitManager(config_path=rem_config_path)
    assert rem.config["name"] == "Test REM Config"
    assert "pips" in rem.config["stop_loss"]


@pytest.mark.parametrize(
    "side, entry_price, atr, expected_sl, expected_tp",
    [
        ("long", 1.1000, 0.0020, 1.0950, 1.1060),
        ("short", 1.1000, 0.0020, 1.1050, 1.0940),
    ],
)
def test_rem_check_exits(
    rem_config_path: Path,
    side: str,
    entry_price: float,
    atr: float,
    expected_sl: float,
    expected_tp: float,
):
    rem = RiskExitManager(config_path=rem_config_path)
    sl_price, tp_price = rem.check_exits(
        position_side=side, entry_price=entry_price, atr=atr
    )
    assert sl_price == pytest.approx(expected_sl)
    assert tp_price == pytest.approx(expected_tp)


def test_rem_pluggable_nature():
    class MockBacktester:
        def __init__(self, rem: RiskExitManager):
            self.rem = rem

        def run(self):
            assert self.rem is not None
            assert self.rem.config["stop_loss"]["pips"] == 100

    config_dict = {"stop_loss": {"pips": 100}}
    config_str = yaml.dump(config_dict)
    rem = RiskExitManager(config_path=StringIO(config_str))
    backtester = MockBacktester(rem=rem)
    backtester.run()


# New tests for execution model refactor (Part 3)


def test_check_exits_with_stop_triggered_returns_descriptor():
    """
    Test check_exits_intrabar returns descriptor when stop-loss triggered.

    When bar low (for long) crosses below stop-loss price, should return
    should_close descriptor with exit_price equal to stop-loss level.
    """
    config_dict = {"stop_loss": {"price_offset": 0.0050}}
    config_str = yaml.dump(config_dict)
    rem = RiskExitManager(config_path=StringIO(config_str))

    # Long position with entry at 1.1000, stop at 1.0950
    position = Position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar where low triggers stop
    current_bar = pd.Series(
        {
            "open": 1.0980,
            "high": 1.0990,
            "low": 1.0940,  # Crosses below stop at 1.0950
            "close": 1.0960,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is not None
    assert result["action"] == "should_close"
    assert result["reason"] == "stop_loss"
    assert result["exit_price"] == pytest.approx(1.0950)


def test_check_exits_with_take_profit_triggered_returns_descriptor():
    """
    Test check_exits_intrabar returns descriptor when take-profit triggered.

    When bar high (for long) crosses above TP price, should return
    should_close descriptor with exit_price equal to TP level.
    """
    config_dict = {"take_profit": {"price_offset": 0.0100}}
    config_str = yaml.dump(config_dict)
    rem = RiskExitManager(config_path=StringIO(config_str))

    # Short position with entry at 1.1000, TP at 1.0900
    position = Position(
        symbol="EURUSD",
        side="short",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar where low triggers TP
    current_bar = pd.Series(
        {
            "open": 1.0920,
            "high": 1.0930,
            "low": 1.0890,  # Crosses below TP at 1.0900
            "close": 1.0910,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is not None
    assert result["action"] == "should_close"
    assert result["reason"] == "take_profit"
    assert result["exit_price"] == pytest.approx(1.0900)


def test_check_exits_with_no_trigger_returns_none():
    """
    Test check_exits_intrabar returns None when neither stop nor TP triggered.

    When bar doesn't cross stop or TP levels, should return None.
    """
    config_dict = {
        "stop_loss": {"price_offset": 0.0050},
        "take_profit": {"price_offset": 0.0100},
    }
    config_str = yaml.dump(config_dict)
    rem = RiskExitManager(config_path=StringIO(config_str))

    # Long position with entry at 1.1000, stop at 1.0950, TP at 1.1100
    position = Position(
        symbol="EURUSD",
        side="long",
        entry_price=1.1000,
        entry_mid_price=1.1000,
        size=100,
        entry_time=datetime(2024, 1, 1),
        bars_held=1,
        mfe_currency=0.0,
        mae_currency=0.0,
        unrealized_pnl=0.0,
        initial_risk_ccy=None,
        context_at_entry=None,
    )

    # Bar that doesn't trigger stop or TP
    current_bar = pd.Series(
        {
            "open": 1.1010,
            "high": 1.1020,
            "low": 1.0990,  # Above stop at 1.0950, below TP at 1.1100
            "close": 1.1005,
        },
        name=datetime(2024, 1, 1, 1),
    )

    result = rem.check_exits_intrabar(position, current_bar)

    assert result is None

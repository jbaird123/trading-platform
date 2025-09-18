from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
import yaml  # type: ignore
from trading_platform.risk_manager.rem import RiskExitManager

# Validates: [REM-6.1], [REM-6.2], [REM-6.3], [REM-6.4]


@pytest.fixture(scope="module")
def rem_config_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Creates a temporary REM config file for testing."""
    config = {
        "name": "Test REM Config",
        "stop_loss": {"type": "static", "pips": 50},
        "take_profit": {"type": "dynamic", "atr_multiplier": 3.0},
    }
    path: Path = tmp_path_factory.mktemp("config") / "rem.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return path


def test_rem_config_loading(rem_config_path: Path):
    """Tests that the REM can be instantiated and loads a config."""
    rem = RiskExitManager(config_path=rem_config_path)
    assert rem.config["name"] == "Test REM Config"
    assert rem.config["stop_loss"]["type"] == "static"


@pytest.mark.parametrize(
    "side, entry_price, current_price, atr, expected_sl, expected_tp",
    [
        # Long position
        ("long", 1.1000, 1.1050, 0.0020, 1.0950, 1.1060),
        # Short position
        ("short", 1.1000, 1.0950, 0.0020, 1.1050, 1.0940),
    ],
)
def test_rem_check_exits(
    rem_config_path: Path,
    side: str,
    entry_price: float,
    current_price: float,
    atr: float,
    expected_sl: float,
    expected_tp: float,
):
    """Tests the core exit calculation logic."""
    rem = RiskExitManager(config_path=rem_config_path)
    sl_price, tp_price = rem.check_exits(
        position_side=side,
        entry_price=entry_price,
        current_price=current_price,
        atr=atr,
    )
    assert sl_price == pytest.approx(expected_sl)
    assert tp_price == pytest.approx(expected_tp)


def test_rem_pluggable_nature():
    """Tests that the REM can be treated as a pluggable component.

    This is a conceptual test to demonstrate that the REM can be initialized
    independently and passed to a consumer (like a mock backtester).
    """

    class MockBacktester:
        def __init__(self, rem: RiskExitManager):
            self.rem = rem

        def run(self):
            # The backtester would use the REM instance internally
            assert self.rem is not None
            assert self.rem.config["stop_loss"]["pips"] == 100

    # 1. Create a config on the fly
    config_dict = {"stop_loss": {"type": "static", "pips": 100}}
    config_str = yaml.dump(config_dict)

    # 2. Initialize REM from the config
    rem = RiskExitManager(config_path=StringIO(config_str))

    # 3. "Plug in" the REM instance to another component
    backtester = MockBacktester(rem=rem)
    backtester.run()

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

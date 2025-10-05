from __future__ import annotations

import pandas as pd
import pytest

from trading_platform.strategy.yaml_strategy import YAMLStrategy


@pytest.fixture
def doji_candle_data() -> pd.DataFrame:
    """Fixture for data containing a Doji candle."""
    data = {
        "open": [100, 105, 110, 110, 112],
        "high": [102, 108, 115, 115, 114],
        "low": [98, 104, 105, 105, 111],
        "close": [101, 106, 110.1, 109.9, 113],
        "volume": [1000] * 5,
    }
    index = pd.to_datetime(
        ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"]
    )
    return pd.DataFrame(data, index=index)


def test_can_use_candlestick_pattern_in_strategy(doji_candle_data):
    """
    Validates: [SE-3.5], [SE-3.6]
    Tests that a candlestick pattern (CDL_DOJI) can be used as a feature
    in a declarative YAML strategy.
    """
    strategy_config = {
        "strategy_name": "Doji Test Strategy",
        "features": [
            {
                "name": "is_doji",
                "type": "CDL_DOJI",
            }
        ],
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "is_doji"},
                        "right": 0,
                    }
                ]
            }
        ],
    }

    strategy = YAMLStrategy(config=strategy_config)
    signals = strategy.generate_signals(doji_candle_data)

    # pandas-ta cdl_doji returns 100 for a doji
    # We expect a 'enter_long' signal on the 3rd bar (index 2)
    assert signals.iloc[2] == "enter_long"
    assert signals.iloc[0] is None
    assert signals.iloc[1] is None
    assert signals.iloc[4] is None
# Validates: [SE-3.4], [SE-3.5]
from __future__ import annotations

import pandas as pd

from trading_platform.strategy.yaml_strategy import compile_strategy

# A single, schema-compliant config for a long/short crossover strategy.
# This will be used by all tests in this file.
CROSSOVER_CFG = {
    "strategy_name": "EMA Crossover",
    "parameters": {},
    "long_entry_rules": [
        {
            "any_of": [
                {
                    "condition": "cross_above",
                    "left": {"ref": "ema_fast"},
                    "right": {"ref": "ema_slow"},
                }
            ]
        }
    ],
    "long_exit_rules": [
        {
            "any_of": [
                {
                    "condition": "cross_below",
                    "left": {"ref": "ema_fast"},
                    "right": {"ref": "ema_slow"},
                }
            ]
        }
    ],
    "short_entry_rules": [
        {
            "any_of": [
                {
                    "condition": "cross_below",
                    "left": {"ref": "ema_fast"},
                    "right": {"ref": "ema_slow"},
                }
            ]
        }
    ],
    "short_exit_rules": [
        {
            "any_of": [
                {
                    "condition": "cross_above",
                    "left": {"ref": "ema_fast"},
                    "right": {"ref": "ema_slow"},
                }
            ]
        }
    ],
}


def test_generate_long_signal_on_crossover():
    """
    Verifies that a 'long' signal is generated when the fast EMA crosses
    above the slow EMA.
    """
    # Setup: Create data where fast EMA crosses above slow EMA
    data = pd.DataFrame(
        {
            "ema_fast": [99.0, 101.0],  # Previous bar, Current bar
            "ema_slow": [100.0, 100.0],
        }
    )

    # Action: Generate signals via YAML strategy
    signals = compile_strategy(CROSSOVER_CFG).generate_signals(data)

    # Assert: Check for 'long' signal on the current (last) bar
    assert signals.iloc[-1] == "long"


def test_generate_short_signal_on_crossunder():
    """
    Verifies that a 'short' signal is generated when the fast EMA crosses
    below the slow EMA.
    """
    # Setup: Create data where fast EMA crosses below slow EMA
    data = pd.DataFrame(
        {
            "ema_fast": [101.0, 99.0],
            "ema_slow": [100.0, 100.0],
        }
    )

    # Action: Generate signals
    signals = compile_strategy(CROSSOVER_CFG).generate_signals(data)

    # Assert: Check for 'short' signal on the current (last) bar
    assert signals.iloc[-1] == "short"


def test_generate_flat_signal_when_no_crossover():
    """
    Verifies that a 'flat' signal is generated when there is no crossover event.
    """
    # Setup: Create data where fast EMA is above slow EMA but not crossing
    data = pd.DataFrame(
        {
            "ema_fast": [101.0, 102.0],
            "ema_slow": [100.0, 100.0],
        }
    )
    signals = compile_strategy(CROSSOVER_CFG).generate_signals(data)
    assert signals.iloc[-1] == "flat"

from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import compile_strategy


def test_yaml_engine_missing_required_fields():
    with pytest.raises(ValueError):
        compile_strategy({})


def test_yaml_engine_unsupported_condition_raises():
    cfg = {
        "strategy_name": "X",
        "entry_rules": [{"any_of": [{"condition": "bad", "left": 1, "right": 2}]}],
        "exit_rules": [{"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}],
    }
    with pytest.raises(ValueError):
        compile_strategy(cfg)


def test_yaml_engine_bearish_entry_only_for_cross():
    # any_of without cross_* should not allow flat->short
    cfg = {
        "strategy_name": "X",
        "entry_rules": [{"any_of": [{"condition": "is_above", "left": 2, "right": 3}]}],
        "exit_rules": [{"any_of": [{"condition": "is_below", "left": 2, "right": 3}]}],
    }
    strat = compile_strategy(cfg)
    assert strat.allow_bearish_entry_from_exit is False

    cfg2 = {
        "strategy_name": "X",
        "entry_rules": [{"any_of": [{"condition": "is_above", "left": 2, "right": 3}]}],
        "exit_rules": [
            {"any_of": [{"condition": "cross_below", "left": 2, "right": 3}]}
        ],
    }
    strat2 = compile_strategy(cfg2)
    assert strat2.allow_bearish_entry_from_exit is True

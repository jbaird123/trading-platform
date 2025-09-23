# Validates: [SE-3.5.3]
from __future__ import annotations

import pytest
from trading_platform.strategy.yaml_strategy import compile_strategy


def test_yaml_engine_missing_required_fields():
    with pytest.raises(ValueError):
        compile_strategy({})


def test_yaml_engine_unsupported_condition_raises():
    cfg = {
        "strategy_name": "X",
        "long_entry_rules": [{"any_of": [{"condition": "bad", "left": 1, "right": 2}]}],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
    }
    with pytest.raises(ValueError):
        compile_strategy(cfg)

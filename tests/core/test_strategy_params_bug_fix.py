"""
Unit test for the strategy_params bug fix.

Tests that strategy_params from the config file are applied to strategy
before compilation, enabling parameter substitution to work correctly.
"""

import pandas as pd


def test_strategy_params_applied_before_compilation(tmp_path):
    """
    Regression test for bug where strategy_params weren't applied before compilation.

    Before fix: baseline used strategy file defaults (12/26)
    After fix: baseline uses config strategy_params (20/80)
    """
    from trading_platform.strategy.yaml_strategy import compile_strategy

    # Create strategy config with defaults 12/26
    strategy_cfg = {
        "strategy_name": "TestEMA",
        "parameters": {
            "ema_fast_length": 12,
            "ema_slow_length": 26,
        },
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": "${ema_fast_length}"},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": "${ema_slow_length}"},
                "source": "close",
            },
        ],
        "long_entry_rules": [
            {
                "all_of": [
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
                "all_of": [
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

    # Simulate what CLI now does: apply strategy_params before compilation
    strategy_params_from_cfg = {"ema_fast_length": 20, "ema_slow_length": 80}

    base_params = strategy_cfg.get("parameters") or {}
    base_params.update(strategy_params_from_cfg)
    strategy_cfg["parameters"] = base_params

    # Compile strategy
    strat = compile_strategy(strategy_cfg)

    # Generate signals on sample data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.1, 1.0] * 20,
            "high": [1.1, 1.2, 1.3, 1.2, 1.1] * 20,
            "low": [0.9, 1.0, 1.1, 1.0, 0.9] * 20,
            "close": [1.05, 1.15, 1.25, 1.15, 1.05] * 20,
            "volume": [100] * 100,
        },
        index=pd.date_range("2024-01-01", periods=100, freq="H"),
    )

    signals = strat.generate_signals(df)

    # Verify EMAs were calculated with 20/80, not 12/26
    feat_df = strat._feature_df

    # Calculate expected EMA values manually
    # EMA formula: EMA_t = (Price_t * K) + (EMA_{t-1} * (1 - K))
    # where K = 2 / (length + 1)

    k_20 = 2 / 21
    k_80 = 2 / 81

    # First bar initializes to price
    assert feat_df.iloc[0]["ema_fast"] == df.iloc[0]["close"]
    assert feat_df.iloc[0]["ema_slow"] == df.iloc[0]["close"]

    # Second bar should use the formula
    expected_fast_1 = (df.iloc[1]["close"] * k_20) + (
        feat_df.iloc[0]["ema_fast"] * (1 - k_20)
    )
    expected_slow_1 = (df.iloc[1]["close"] * k_80) + (
        feat_df.iloc[0]["ema_slow"] * (1 - k_80)
    )

    assert (
        abs(feat_df.iloc[1]["ema_fast"] - expected_fast_1) < 1e-10
    ), f"EMA fast not using length=20: expected {expected_fast_1}, got {feat_df.iloc[1]['ema_fast']}"
    assert (
        abs(feat_df.iloc[1]["ema_slow"] - expected_slow_1) < 1e-10
    ), f"EMA slow not using length=80: expected {expected_slow_1}, got {feat_df.iloc[1]['ema_slow']}"


def test_strategy_params_not_applied_uses_defaults():
    """
    Test that without applying strategy_params, strategy uses file defaults.

    This documents the pre-fix behavior.
    """
    from trading_platform.strategy.yaml_strategy import compile_strategy

    # Create strategy config with defaults 12/26
    strategy_cfg = {
        "strategy_name": "TestEMA",
        "parameters": {
            "ema_fast_length": 12,
            "ema_slow_length": 26,
        },
        "features": [
            {
                "name": "ema_fast",
                "type": "EMA",
                "params": {"length": "${ema_fast_length}"},
                "source": "close",
            },
            {
                "name": "ema_slow",
                "type": "EMA",
                "params": {"length": "${ema_slow_length}"},
                "source": "close",
            },
        ],
        "long_entry_rules": [
            {
                "all_of": [
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
                "all_of": [
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

    # DON'T apply strategy_params - should use defaults

    # Compile strategy
    strat = compile_strategy(strategy_cfg)

    # Generate signals on sample data
    df = pd.DataFrame(
        {
            "open": [1.0, 1.1, 1.2, 1.1, 1.0] * 20,
            "high": [1.1, 1.2, 1.3, 1.2, 1.1] * 20,
            "low": [0.9, 1.0, 1.1, 1.0, 0.9] * 20,
            "close": [1.05, 1.15, 1.25, 1.15, 1.05] * 20,
            "volume": [100] * 100,
        },
        index=pd.date_range("2024-01-01", periods=100, freq="H"),
    )

    signals = strat.generate_signals(df)

    # Verify EMAs were calculated with 12/26 (defaults)
    feat_df = strat._feature_df

    k_12 = 2 / 13
    k_26 = 2 / 27

    # Second bar should use the formula with default lengths
    expected_fast_1 = (df.iloc[1]["close"] * k_12) + (
        feat_df.iloc[0]["ema_fast"] * (1 - k_12)
    )
    expected_slow_1 = (df.iloc[1]["close"] * k_26) + (
        feat_df.iloc[0]["ema_slow"] * (1 - k_26)
    )

    assert (
        abs(feat_df.iloc[1]["ema_fast"] - expected_fast_1) < 1e-10
    ), "EMA fast not using default length=12"
    assert (
        abs(feat_df.iloc[1]["ema_slow"] - expected_slow_1) < 1e-10
    ), "EMA slow not using default length=26"

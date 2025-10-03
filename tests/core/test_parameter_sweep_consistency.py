"""
Test to ensure parameter sweep produces consistent results with standalone backtests.

This test addresses a critical bug where parameter sweeps produced different results
than standalone runs due to strategy_params not being applied before
baseline compilation.
"""

import json
from argparse import Namespace

import pandas as pd
import pytest
from trading_platform.cli import cmd_run_backtest


@pytest.fixture(autouse=True)
def mock_load_instrument_data(monkeypatch):
    def _mock_load_instrument_data(symbol, data_root):
        num_rows = 100
        dates = pd.to_datetime(pd.date_range(start="2024-01-01", periods=num_rows, freq="h"), utc=True)
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [1.1 + i * 0.01 for i in range(num_rows)],
            "high": [1.1 + i * 0.01 for i in range(num_rows)],
            "low": [1.1 + i * 0.01 for i in range(num_rows)],
            "close": [1.1 + i * 0.01 for i in range(num_rows)],
            "volume": [100] * num_rows
        })
        df = df.set_index("timestamp")
        return df, []

    monkeypatch.setattr("trading_platform.data.handler.load_instrument_data", _mock_load_instrument_data)


def test_parameter_sweep_matches_standalone(tmp_path, monkeypatch):
    """
    Test that a parameter sweep with a single parameter set produces
    identical results to a standalone backtest with the same parameters.

    This verifies the fix for the bug where sweep used strategy file defaults
    while standalone used config parameters.
    """
    # Create a minimal strategy config
    strategy_config = {
        "strategy_name": "TestStrategy",
        "parameters": {
            "ema_fast_length": 12,  # Default in file
            "ema_slow_length": 26,  # Default in file
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

    # Save strategy to temp file
    strategy_path = tmp_path / "strategy.json"
    with open(strategy_path, "w") as f:
        json.dump(strategy_config, f)

    # Config with parameter sweep (single parameter set)
    sweep_config = {
        "user_id": "test",
        "runs_dir": str(tmp_path / "runs_sweep"),
        "initial_cash": 100000,
        "position_size": 10000,
        "warmup_bars": 50,
        "data_request": {
            "symbol": "EUR_USD",
            "timeframe": "1H",
            "start": "2024-01-01",
            "end": "2024-03-31",
        },
        "strategy_path": str(strategy_path),
        "strategy_params": {
            "ema_fast_length": 20,  # Override to 20
            "ema_slow_length": 80,  # Override to 80
        },
        "parameter_search": {
            "objective": "total_pnl",
            "grid": {
                "ema_fast_length": [20],  # Single value
                "ema_slow_length": [80],  # Single value
            },
        },
    }

    # Standalone config (no parameter search)
    standalone_config = {
        "user_id": "test",
        "runs_dir": str(tmp_path / "runs_standalone"),
        "initial_cash": 100000,
        "position_size": 10000,
        "warmup_bars": 50,
        "data_request": {
            "symbol": "EUR_USD",
            "timeframe": "1H",
            "start": "2024-01-01",
            "end": "2024-03-31",
        },
        "strategy_path": str(strategy_path),
        "strategy_params": {
            "ema_fast_length": 20,
            "ema_slow_length": 80,
        },
    }

    # Save configs
    sweep_config_path = tmp_path / "sweep_config.json"
    standalone_config_path = tmp_path / "standalone_config.json"

    with open(sweep_config_path, "w") as f:
        json.dump(sweep_config, f)
    with open(standalone_config_path, "w") as f:
        json.dump(standalone_config, f)

    # Change to tmp directory for runs
    monkeypatch.chdir(tmp_path)

    # Run sweep in demo mode (generates synthetic data)
    ns_sweep = Namespace(demo=False, user="test", config=str(sweep_config_path))
    cmd_run_backtest(ns_sweep)

    # Run standalone in demo mode
    ns_standalone = Namespace(demo=False, user="test", config=str(standalone_config_path))
    cmd_run_backtest(ns_standalone)

    # Load results
    sweep_runs = list((tmp_path / "runs_sweep" / "test").glob("run_*"))
    standalone_runs = list((tmp_path / "runs_standalone" / "test").glob("run_*"))

    assert len(sweep_runs) == 1, "Expected exactly one sweep run"
    assert len(standalone_runs) == 1, "Expected exactly one standalone run"

    sweep_brief_path = sweep_runs[0] / "brief.json"
    standalone_brief_path = standalone_runs[0] / "brief.json"

    with open(sweep_brief_path) as f:
        sweep_brief = json.load(f)
    with open(standalone_brief_path) as f:
        standalone_brief = json.load(f)

    # Compare results
    sweep_pnl = sweep_brief["parameter_search"]["top"]["score"]
    sweep_baseline_pnl = sweep_brief["overall_performance"]["total_pnl"]
    standalone_pnl = standalone_brief["overall_performance"]["total_pnl"]

    sweep_trades = sweep_brief["overall_performance"]["n_trades"]
    standalone_trades = standalone_brief["overall_performance"]["n_trades"]

    # Results should be identical
    assert (
        abs(sweep_pnl - standalone_pnl) < 0.01
    ), f"Sweep result ({sweep_pnl}) differs from standalone ({standalone_pnl})"
    assert abs(sweep_baseline_pnl - standalone_pnl) < 0.01, (
        f"Sweep baseline ({sweep_baseline_pnl}) differs from standalone "
        f"({standalone_pnl})"
    )
    assert (
        sweep_trades == standalone_trades
    ), f"Trade counts differ: sweep={sweep_trades}, standalone={standalone_trades}"


def test_strategy_params_override_file_defaults(tmp_path, monkeypatch):
    """
    Test that strategy_params in the config override the strategy file's
    default parameters.

    This test ensures parameter substitution works correctly when strategy_params
    are specified in the run config.
    """
    # Strategy with defaults 12/26
    strategy_config = {
        "strategy_name": "TestStrategy",
        "parameters": {"ema_fast_length": 12, "ema_slow_length": 26},
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

    strategy_path = tmp_path / "strategy.json"
    with open(strategy_path, "w") as f:
        json.dump(strategy_config, f)

    # Run with overridden params 20/80
    run_config = {
        "user_id": "test",
        "runs_dir": str(tmp_path / "runs"),
        "initial_cash": 100000,
        "position_size": 10000,
        "warmup_bars": 50,
        "data_request": {
            "symbol": "EUR_USD",
            "timeframe": "1H",
            "start": "2024-01-01",
            "end": "2024-02-29",
        },
        "strategy_path": str(strategy_path),
        "strategy_params": {
            "ema_fast_length": 20,  # Should override 12
            "ema_slow_length": 80,  # Should override 26
        },
    }

    config_path = tmp_path / "config.json"
    with open(config_path, "w") as f:
        json.dump(run_config, f)

    monkeypatch.chdir(tmp_path)

    ns = Namespace(demo=False, user="test", config=str(config_path))
    cmd_run_backtest(ns)

    # Check that features were computed with 20/80, not 12/26
    runs = list((tmp_path / "runs" / "test").glob("run_*"))
    assert len(runs) == 1

    features_path = runs[0] / "features.json"
    with open(features_path) as f:
        features_data = json.load(f)

    # Extract EMA values and verify they match 20/80 calculations
    ema_fast_series = features_data["series"]["ema_fast"]
    ema_slow_series = features_data["series"]["ema_slow"]

    # Load price data
    prices_path = runs[0] / "prices.csv"
    prices = pd.read_csv(prices_path, index_col=0, parse_dates=True)

    # Check second bar (first bar after initialization)
    # EMA formula: EMA_t = (Price_t * K) + (EMA_{t-1} * (1 - K))
    # where K = 2 / (length + 1)

    k_20 = 2 / 21
    k_80 = 2 / 81

    # Get values
    ema_fast_0 = ema_fast_series[0][1]  # First value
    ema_slow_0 = ema_slow_series[0][1]
    ema_fast_1 = ema_fast_series[1][1]  # Second value
    ema_slow_1 = ema_slow_series[1][1]

    price_1 = prices.iloc[1]["close"]

    # Calculate expected values
    expected_fast_1 = (price_1 * k_20) + (ema_fast_0 * (1 - k_20))
    expected_slow_1 = (price_1 * k_80) + (ema_slow_0 * (1 - k_80))

    # Verify (allow small floating point tolerance)
    assert (
        abs(ema_fast_1 - expected_fast_1) < 1e-6
    ), f"EMA fast not using length=20: expected {expected_fast_1}, got {ema_fast_1}"
    assert (
        abs(ema_slow_1 - expected_slow_1) < 1e-6
    ), f"EMA slow not using length=80: expected {expected_slow_1}, got {ema_slow_1}"

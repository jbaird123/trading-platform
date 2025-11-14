"""
Test to ensure parameter sweep produces consistent results with standalone backtests.

This test addresses a critical bug where parameter sweeps produced different results
than standalone runs due to strategy_params not being applied before
baseline compilation.
"""

import json
from argparse import Namespace

import numpy as np
import pandas as pd
import pytest
from ta.trend import EMAIndicator
from trading_platform.cli import cmd_run_backtest


@pytest.fixture(autouse=True)
def mock_load_and_extend_data(monkeypatch):
    """Mock data loading to provide sufficient warmup bars automatically."""

    def _mock_load_instrument_data(symbol, data_root):
        # Return a large dataset that covers warmup needs
        # DataHandler will slice this based on start/end + warmup calculation
        num_rows = 500  # Enough for any reasonable warmup
        dates = pd.to_datetime(
            pd.date_range(start="2023-12-20", periods=num_rows, freq="h"),
            utc=True,
        )
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [1.1 + i * 0.01 for i in range(num_rows)],
                "high": [1.1 + i * 0.01 for i in range(num_rows)],
                "low": [1.1 + i * 0.01 for i in range(num_rows)],
                "close": [1.1 + i * 0.01 for i in range(num_rows)],
                "volume": [100] * num_rows,
            }
        )
        df = df.set_index("timestamp")
        return df, []

    monkeypatch.setattr(
        "trading_platform.data.handler.load_instrument_data",
        _mock_load_instrument_data,
    )


def _feature_series(series_list):
    """Convert feature series (list of [timestamp, value]) to pandas Series."""
    times = [pd.to_datetime(entry[0], utc=True) for entry in series_list]
    values = [entry[1] for entry in series_list]
    return pd.Series(values, index=times, dtype="float64")


def _series_error(series: pd.Series, expected: pd.Series) -> float:
    """Compute mean absolute difference between feature series and expectation."""
    series_vals = series.dropna().to_numpy()
    expected_vals = expected.dropna().to_numpy()
    common = min(len(series_vals), len(expected_vals))
    if common == 0:
        return float("inf")
    diff = np.abs(series_vals[:common] - expected_vals[:common])
    return float(np.nanmean(diff))


def test_parameter_sweep_matches_standalone(tmp_path, monkeypatch):
    """
    Test that a parameter sweep with a single parameter set produces
    identical results to a standalone backtest with the same parameters.

    This verifies the fix for the bug where sweep used strategy file defaults
    while standalone used config parameters.
    """
    # Mock the centralized RUNS_DIR and WORKSPACE_DIR to use temp directory
    # Mock both in paths and in config to handle default value resolution
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.paths.WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.config.paths.RUNS_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.config.paths.WORKSPACE_DIR", tmp_path)

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
        "user_id": "sweep",
        "initial_cash": 100000,
        "position_size": 10000,
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
        "user_id": "standalone",
        "initial_cash": 100000,
        "position_size": 10000,
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

    # Run sweep in demo mode (generates synthetic data)
    ns_sweep = Namespace(demo=False, user="sweep", config=str(sweep_config_path))
    cmd_run_backtest(ns_sweep)

    # Run standalone in demo mode
    ns_standalone = Namespace(
        demo=False, user="standalone", config=str(standalone_config_path)
    )
    cmd_run_backtest(ns_standalone)

    # Load results from centralized runs directory
    sweep_runs = list((tmp_path / "sweep").glob("run_*"))
    standalone_runs = list((tmp_path / "standalone").glob("run_*"))

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

    # Verify sweep and standalone produce identical EMA feature sequences
    sweep_features = json.load(open(sweep_runs[0] / "features.json"))
    standalone_features = json.load(open(standalone_runs[0] / "features.json"))

    sweep_fast = _feature_series(sweep_features["series"]["ema_fast"])
    standalone_fast = _feature_series(standalone_features["series"]["ema_fast"])
    sweep_slow = _feature_series(sweep_features["series"]["ema_slow"])
    standalone_slow = _feature_series(standalone_features["series"]["ema_slow"])

    # Ensure sweep and standalone feature series are identical in value order
    sweep_fast_vals = sweep_fast.dropna().to_numpy()
    standalone_fast_vals = standalone_fast.dropna().to_numpy()
    sweep_slow_vals = sweep_slow.dropna().to_numpy()
    standalone_slow_vals = standalone_slow.dropna().to_numpy()

    common_fast = min(len(sweep_fast_vals), len(standalone_fast_vals))
    common_slow = min(len(sweep_slow_vals), len(standalone_slow_vals))
    np.testing.assert_allclose(
        sweep_fast_vals[:common_fast],
        standalone_fast_vals[:common_fast],
        atol=1e-12,
        rtol=1e-12,
    )
    np.testing.assert_allclose(
        sweep_slow_vals[:common_slow],
        standalone_slow_vals[:common_slow],
        atol=1e-12,
        rtol=1e-12,
    )


def test_strategy_params_override_file_defaults(tmp_path, monkeypatch):
    """
    Test that strategy_params in the config override the strategy file's
    default parameters.

    This test ensures parameter substitution works correctly when strategy_params
    are specified in the run config.
    """
    # Mock the centralized RUNS_DIR and WORKSPACE_DIR to use temp directory
    # Mock both in paths and in config to handle default value resolution
    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.paths.WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.config.paths.RUNS_DIR", tmp_path)
    monkeypatch.setattr("trading_platform.core.config.paths.WORKSPACE_DIR", tmp_path)

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
        "initial_cash": 100000,
        "position_size": 10000,
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

    ns = Namespace(demo=False, user="test", config=str(config_path))
    cmd_run_backtest(ns)

    # Check that features were computed with 20/80, not 12/26
    runs = list((tmp_path / "test").glob("run_*"))
    assert len(runs) == 1, f"Expected 1 run, found {len(runs)}"

    features_path = runs[0] / "features.json"
    with open(features_path) as f:
        features_data = json.load(f)

    # Extract EMA values and verify they match 20/80 calculations
    ema_fast_series = _feature_series(features_data["series"]["ema_fast"])
    ema_slow_series = _feature_series(features_data["series"]["ema_slow"])

    prices = pd.read_csv(runs[0] / "prices.csv", index_col=0, parse_dates=True)
    expected_fast = EMAIndicator(
        close=prices["close"], window=20, fillna=False
    ).ema_indicator()
    expected_slow = EMAIndicator(
        close=prices["close"], window=80, fillna=False
    ).ema_indicator()

    expected_fast_default = EMAIndicator(
        close=prices["close"], window=12, fillna=False
    ).ema_indicator()
    expected_slow_default = EMAIndicator(
        close=prices["close"], window=26, fillna=False
    ).ema_indicator()

    err_fast_override = _series_error(ema_fast_series, expected_fast)
    err_fast_default = _series_error(ema_fast_series, expected_fast_default)
    err_slow_override = _series_error(ema_slow_series, expected_slow)
    err_slow_default = _series_error(ema_slow_series, expected_slow_default)

    assert err_fast_override * 0.1 < err_fast_default, (
        "EMA fast closer to default length: "
        f"override_err={err_fast_override}, default_err={err_fast_default}"
    )
    assert err_slow_override * 0.1 < err_slow_default, (
        "EMA slow closer to default length: "
        f"override_err={err_slow_override}, default_err={err_slow_default}"
    )

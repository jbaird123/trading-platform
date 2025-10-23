from __future__ import annotations

import json
import os
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest


@pytest.fixture
def cli_stubs(monkeypatch, tmp_path):
    import trading_platform.cli as cli

    run_path = tmp_path / "run"
    run_path.mkdir()
    calls: dict[str, Any] = {}

    class DummyRunConfig:
        @staticmethod
        def model_validate(data: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(
                run_id=data.get("run_id", "rid"),
                run_seed=data.get("run_seed", 11),
                rmm_config=data.get("rmm_config"),
                blackout_utc=data.get("blackout_utc", []),
                blackout_events=data.get("blackout_events", []),
            )

    monkeypatch.setattr(cli, "RunConfig", DummyRunConfig)
    monkeypatch.setattr(cli, "initialize_run", lambda cfg: run_path)
    monkeypatch.setattr(cli, "_get_git_commit", lambda: "abc123")

    class MockDataHandler:
        def __init__(self, symbol, data_root, instrument):
            self.data_quality_flags = ["mock_dq_flag"]

        def get_data(self, timeframe, start, end):
            df = pd.DataFrame(
                {"close": [1.0, 2.0, 3.0]},
                index=pd.date_range("2024-01-01", periods=3, freq="h"),
            )
            df_any = cast(Any, df)
            df_any.to_parquet = lambda *args, **kwargs: None
            return df_any

    monkeypatch.setattr("trading_platform.cli.DataHandler", MockDataHandler)

    def fake_get_instrument_definition(symbol: str):
        from datetime import time

        from trading_platform.data.instrument import (
            InstrumentDefinition,
            SessionDefinition,
        )

        return InstrumentDefinition(
            asset_class="Forex",
            point_value=1.0,
            tick_size=0.00001,
            pip_location=0.0001,
            commission_model={"type": "spread"},
            sessions=[
                SessionDefinition(
                    close_time=time(17, 0), close_timezone="America/New_York"
                )
            ],
            symbol="TEST",
        )

    monkeypatch.setattr(
        cli, "get_instrument_definition", fake_get_instrument_definition
    )

    class DummyStrategy:
        def __init__(self) -> None:
            self.name = "dummy"
            self.features = [{"name": "ema", "params": {"length": 5}}]
            self._feature_df = pd.DataFrame({"ema": [1.0, 2.0, 3.0]})

        def generate_signals(self, df: pd.DataFrame):
            calls["signals_input"] = df
            return pd.Series([1, 0, -1], index=df.index)

    monkeypatch.setattr(cli, "compile_strategy", lambda cfg: DummyStrategy())

    def fake_run_backtest(**kwargs):
        calls["run_backtest"] = kwargs
        return (
            [SimpleNamespace(entry=datetime(2024, 1, 1))],
            [(datetime(2024, 1, 1), 1.0)],
            [{"reason": "skip"}],
        )

    monkeypatch.setattr(cli, "run_backtest", fake_run_backtest)

    monkeypatch.setattr(
        cli,
        "RiskExitManager",
        lambda config=None, instrument=None: SimpleNamespace(config=config),
    )

    class DummyRMMEngine:
        def __init__(self, config: Any) -> None:
            # Accept either dict or Pydantic model for testing flexibility
            if hasattr(config, "model_dump"):
                calls["rmm_validated"] = config.model_dump()
                self.config = config
            else:
                calls["rmm_validated"] = config
                self.config = config

        def classify_daily(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {"label": ["up"], "confidence": [0.7]},
                index=[df.index[0]],
            )

        def project_to_index(self, daily, index, policy):
            return pd.DataFrame(
                {
                    "label": ["up"] * len(index),
                    "confidence": [0.7] * len(index),
                    "allowed_sides": [["long", "short"]] * len(index),
                },
                index=index,
            )

    monkeypatch.setattr(cli, "RMMEngine", DummyRMMEngine)
    monkeypatch.setattr(cli, "save_prices_csv", lambda *a, **k: None)
    monkeypatch.setattr(cli, "save_features_for_chart", lambda *a, **k: None)
    monkeypatch.setattr(cli, "run_parameter_sweep", lambda *a, **k: {"ps": 1})
    monkeypatch.setattr(
        cli,
        "walk_forward_optimize_and_test",
        lambda *a, **k: {"wf": 1},
    )
    monkeypatch.setattr(
        cli,
        "finalize_run",
        lambda *a, **k: calls.update({"finalize": k}),
    )

    def fake_monte_carlo(df, cfg_raw, strat_cfg, **_kwargs):
        calls["monte_carlo"] = True
        return {"mc": 1}

    monkeypatch.setattr(
        "trading_platform.core.sweeps.monte_carlo_resimulation",
        fake_monte_carlo,
    )

    return cli, run_path, calls


def test_cmd_run_backtest_full_branch(cli_stubs, tmp_path):
    cli, run_path, calls = cli_stubs

    strat_path = tmp_path / "strat.json"
    strat_path.write_text(
        '{"strategy_name": "S", "long_entry_rules": [{"any_of": []}],'
        ' "long_exit_rules": [{"any_of": []}], "features": '
        '[{"name": "ema", "params": {"length": 3}}], "parameters": {"p": 1}}'
    )
    cfg = {
        "run_id": "rid",
        "run_seed": 5,
        "data_request": {"symbol": "EURUSD"},
        "strategy_path": str(strat_path),
        "strategy_overrides": {
            "parameters": {"p": 2},
            "features": {"ema": {"length": 10}},
        },
        "rem_config": {"name": "rem"},
        "rmm_config": {
            "regimes": [
                {
                    "label": "test",
                    "confidence": 0.9,
                    "conditions": {
                        "all_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    },
                }
            ]
        },
        "parameter_search": {"grid": {"p": [1, 2]}},
        "walk_forward": {"window": 1, "step": 1},
        "monte_carlo": {"mode": "bar_bootstrap", "trials": 2},
        "return_exposure": True,
        "return_skips": True,
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(pd.Series(cfg).to_json())

    ns = Namespace(demo=False, user="user", config=str(cfg_path))
    rc = cli.cmd_run_backtest(ns)

    assert rc == 0
    assert calls["run_backtest"]["return_exposure"] is True
    assert run_path.joinpath("rmm_spans.json").exists()


def test_cmd_run_backtest_fast_mode_last_days_and_overrides(
    cli_stubs, tmp_path, monkeypatch
):
    cli, run_path, calls = cli_stubs

    class MockDataHandler:
        def __init__(self, symbol, data_root, instrument):
            self.data_quality_flags = []

        def get_data(self, timeframe, start, end):
            idx = pd.date_range("2024-01-01", periods=4, freq="h")
            return pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}, index=idx)

    monkeypatch.setattr("trading_platform.cli.DataHandler", MockDataHandler)
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: None,
        raising=False,
    )

    compiled_cfg: dict[str, Any] = {}

    class DFStrategy:
        def __init__(self) -> None:
            self.name = "override"
            self.features = [{"name": "ema", "params": {"length": 1}}]
            self._feature_df = pd.DataFrame({"ema": [1.0, 2.0, 3.0, 4.0]})

        def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame({"sig": [1, 0, 0, 1]}, index=df.index)

    def capture_compile(cfg: dict[str, Any]) -> DFStrategy:
        compiled_cfg.update(cfg)
        return DFStrategy()

    monkeypatch.setattr(cli, "compile_strategy", capture_compile)

    class TransitionRMM:
        def __init__(self, config: Any) -> None:
            # Accept either dict or Pydantic model for testing flexibility
            if hasattr(config, "model_dump"):
                calls["rmm_transition"] = config.model_dump()
                self.config = config
            else:
                calls["rmm_transition"] = config
                self.config = config

        def classify_daily(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {"label": ["a"], "confidence": [0.9]},
                index=[df.index[0]],
            )

        def project_to_index(self, daily, index, policy):
            modes = [["long"], ["short"], [], ["long", "short"]]
            return pd.DataFrame(
                {
                    "label": ["a"] * len(index),
                    "confidence": [0.9] * len(index),
                    "allowed_sides": modes[: len(index)],
                },
                index=index,
            )

    monkeypatch.setattr(cli, "RMMEngine", TransitionRMM)

    cfg = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "rmm_config": {
            "regimes": [
                {
                    "label": "a",
                    "confidence": 0.9,
                    "conditions": {
                        "all_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    },
                }
            ]
        },
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
            "features": [{"name": "ema", "params": {"length": 1}}],
            "parameters": {"p": 1},
        },
        "strategy_overrides": {
            "parameters": {"p": 2},
            "features": {"ema": {"length": 10}},
        },
        "rem_config": {"name": "rem"},
        "monte_carlo": {"mode": "bar_bootstrap", "trials": 2},
        "return_exposure": True,
        "return_skips": True,
        "strategy_params": {"user": 7},
    }
    cfg_path = tmp_path / "cfg_last_days.json"
    cfg_path.write_text(json.dumps(cfg))

    ns = Namespace(demo=False, user="user", config=str(cfg_path))
    assert cli.cmd_run_backtest(ns) == 0

    assert compiled_cfg["parameters"]["p"] == 2
    assert compiled_cfg["features"][0]["params"]["length"] == 10
    spans = json.loads((run_path / "rmm_spans.json").read_text())
    assert {item["mode"] for item in spans} >= {"both", "long_only", "short_only"}
    market_data = calls["run_backtest"]["market_data"]
    assert isinstance(market_data.index, pd.DatetimeIndex)
    # fast_mode removed - no longer filtering by last_days
    assert "rmm_transition" in calls


def test_cmd_run_backtest_fast_mode_limit_and_exception(
    cli_stubs, tmp_path, monkeypatch
):
    """Test basic backtest run - fast_mode removed."""
    cli, _, calls = cli_stubs

    class MockDataHandler:
        def __init__(self, symbol, data_root, instrument):
            self.data_quality_flags = []

        def get_data(self, timeframe, start, end):
            return pd.DataFrame({"close": list(range(6))})

    monkeypatch.setattr("trading_platform.cli.DataHandler", MockDataHandler)
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: None,
        raising=False,
    )

    strategy_cfg = {
        "strategy_name": "S",
        "long_entry_rules": [{"any_of": []}],
        "long_exit_rules": [{"any_of": []}],
    }

    class MatchingStrategy:
        def __init__(self) -> None:
            self.name = "match"
            self.features: list[dict[str, Any]] = []
            self._feature_df = None

        def generate_signals(self, df: pd.DataFrame) -> pd.Series:
            return pd.Series([1] * len(df), index=df.index)

    monkeypatch.setattr(cli, "compile_strategy", lambda cfg: MatchingStrategy())

    cfg = {
        "run_id": "rid_simple",
        "data_request": {"symbol": "EURUSD"},
        "strategy": strategy_cfg,
    }
    cfg_path = tmp_path / "cfg_simple.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="user", config=str(cfg_path))
    assert cli.cmd_run_backtest(ns) == 0

    market_data = calls["run_backtest"]["market_data"]
    assert len(market_data) == 6  # No filtering without fast_mode


def test_cmd_run_backtest_tuple_variants(cli_stubs, tmp_path, monkeypatch):
    cli, _, calls = cli_stubs
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: None,
        raising=False,
    )

    cfg = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
            "parameters": {"p": 3},
        },
    }
    cfg_path = tmp_path / "cfg_tuple.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="user", config=str(cfg_path))

    def tuple_two(**kwargs):
        return (
            [SimpleNamespace(entry=datetime(2024, 1, 1))],
            [(datetime(2024, 1, 1), 1.0)],
        )

    monkeypatch.setattr(cli, "run_backtest", tuple_two)
    assert cli.cmd_run_backtest(ns) == 0
    assert calls["finalize"]["skipped_trades"] == []

    def list_result(**kwargs):
        return [SimpleNamespace(entry=datetime(2024, 1, 1))]

    monkeypatch.setattr(cli, "run_backtest", list_result)
    assert cli.cmd_run_backtest(ns) == 0
    assert calls["finalize"]["exposure_curve"] == []


def test_cmd_run_backtest_fast_mode_not_dict(cli_stubs, tmp_path, monkeypatch):
    """Test basic backtest - fast_mode removed."""
    cli, _, _ = cli_stubs
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: None,
        raising=False,
    )

    cfg = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
        },
    }
    cfg_path = tmp_path / "cfg_simple_2.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="user", config=str(cfg_path))

    assert cli.cmd_run_backtest(ns) == 0


def test_cmd_run_backtest_override_branch_variants(cli_stubs, tmp_path, monkeypatch):
    cli, _, _ = cli_stubs
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: None,
        raising=False,
    )

    base_strategy = {
        "strategy_name": "S",
        "long_entry_rules": [{"any_of": []}],
        "long_exit_rules": [{"any_of": []}],
        "features": [{"name": "ema", "params": {"length": 1}}],
        "parameters": {"length": 1},
    }

    def clone(obj: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(json.dumps(obj)))

    configs = [
        {
            "run_id": "over0",
            "data_request": {"symbol": "EURUSD"},
            "strategy": clone(base_strategy),
            "strategy_overrides": "noop",
        },
        {
            "run_id": "over1",
            "data_request": {"symbol": "EURUSD"},
            "strategy": clone(base_strategy),
            "strategy_overrides": {"parameters": 1},
        },
        {
            "run_id": "over2",
            "data_request": {"symbol": "EURUSD"},
            "strategy": {
                "strategy_name": "S",
                "long_entry_rules": [{"any_of": []}],
                "long_exit_rules": [{"any_of": []}],
                "features": [{"name": "ema", "params": {"length": 1}}],
                "parameters": 1,
            },
        },
        {
            "run_id": "over3",
            "data_request": {"symbol": "EURUSD"},
            "strategy": clone(base_strategy),
            "strategy_overrides": {"features": 1},
        },
        {
            "run_id": "over4",
            "data_request": {"symbol": "EURUSD"},
            "strategy": {
                "strategy_name": "S",
                "long_entry_rules": [{"any_of": []}],
                "long_exit_rules": [{"any_of": []}],
                "features": [{"name": "ema", "params": 1}],
            },
            "strategy_overrides": {"features": {"ema": {"length": 3}}},
        },
    ]

    for idx, cfg in enumerate(configs):
        cfg_path = tmp_path / f"cfg_overrides_{idx}.json"
        cfg_path.write_text(json.dumps(cfg))
        ns = Namespace(demo=False, user="user", config=str(cfg_path))
        assert cli.cmd_run_backtest(ns) == 0


def test_cmd_run_backtest_with_paths_and_failures(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    run_path = tmp_path / "run_paths"
    monkeypatch.setattr(cli, "initialize_run", lambda cfg: run_path)
    monkeypatch.setattr(cli, "_get_git_commit", lambda: "hash")

    rem_file = tmp_path / "rem.json"
    rem_file.write_text(json.dumps({"name": "rem_file"}))
    rmm_file = tmp_path / "rmm.json"
    rmm_file.write_text(
        json.dumps(
            {
                "regimes": [
                    {
                        "label": "a",
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [
                                {"condition": "is_above", "left": "close", "right": 1.0}
                            ]
                        },
                    }
                ]
            }
        )
    )

    config = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
            "features": [{"name": "ema", "params": {"length": 1}}],
            "parameters": {"length": 1},
        },
        "strategy_overrides": {"features": {"ema": {"length": 2}}},
        "rem_path": str(rem_file),
        "rmm_path": str(rmm_file),
        "return_skips": True,
    }

    def fake_load(path: Path) -> dict[str, Any]:
        if path == rem_file:
            return {"name": "rem_file"}
        if path == rmm_file:
            return {
                "regimes": [
                    {
                        "label": "a",
                        "confidence": 0.9,
                        "conditions": {
                            "all_of": [
                                {"condition": "is_above", "left": "close", "right": 1.0}
                            ]
                        },
                    }
                ]
            }
        return config

    monkeypatch.setattr(cli, "_load_config", fake_load)

    class DummyRunConfig:
        @staticmethod
        def model_validate(data: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(
                run_id=data["run_id"],
                run_seed=1,
                rmm_config=data.get("rmm_config"),
                blackout_utc=[],
                blackout_events=[],
            )

    monkeypatch.setattr(cli, "RunConfig", DummyRunConfig)

    class MockDataHandler:
        def __init__(self, symbol, data_root, instrument):
            self.data_quality_flags = []

        def get_data(self, timeframe, start, end):
            idx = pd.date_range("2024-01-01", periods=6, freq="h")
            return pd.DataFrame({"close": range(6)}, index=idx)

    monkeypatch.setattr("trading_platform.cli.DataHandler", MockDataHandler)
    monkeypatch.setattr(
        pd.DataFrame,
        "to_parquet",
        lambda self, path: run_path.joinpath(path.name).write_text("ok"),
        raising=False,
    )

    compiled_cfg: dict[str, Any] = {}

    class PathStrategy:
        def __init__(self) -> None:
            self.name = "paths"
            self.features = [{"name": "ema", "params": {"length": 1}}]
            self._feature_df = pd.DataFrame({"ema": [1, 2, 3, 4, 5, 6]})

        def generate_signals(self, df: pd.DataFrame) -> pd.Series:
            return pd.Series(range(len(df)), index=df.index)

    def compile_capture(cfg: dict[str, Any]) -> PathStrategy:
        compiled_cfg.update(cfg)
        return PathStrategy()

    monkeypatch.setattr(cli, "compile_strategy", compile_capture)

    monkeypatch.setattr(
        cli,
        "RiskExitManager",
        lambda config=None, instrument=None: SimpleNamespace(config=config),
    )

    class SpanRMM:
        def __init__(self, config: Any) -> None:
            # Accept either dict or Pydantic model for testing flexibility
            self.config = config

        def classify_daily(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {"label": ["a"], "confidence": [0.6]},
                index=[df.index[0]],
            )

        def project_to_index(self, daily, index, policy):
            modes = [["long"], ["short"], [], ["long", "short"], ["long"], []]
            return pd.DataFrame(
                {
                    "label": ["a"] * len(index),
                    "confidence": [0.6] * len(index),
                    "allowed_sides": modes[: len(index)],
                },
                index=index,
            )

    monkeypatch.setattr(cli, "RMMEngine", SpanRMM)
    monkeypatch.setattr(
        cli,
        "save_prices_csv",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("csv")),
    )
    monkeypatch.setattr(
        cli,
        "save_features_for_chart",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("features")),
    )
    monkeypatch.setattr(cli, "run_parameter_sweep", lambda *a, **k: None)
    monkeypatch.setattr(cli, "walk_forward_optimize_and_test", lambda *a, **k: None)
    monkeypatch.setattr(
        "trading_platform.core.sweeps.monte_carlo_resimulation",
        lambda *a, **k: None,
    )

    state: dict[str, Any] = {}

    def run_backtest(**kwargs):
        state["market_len"] = len(kwargs["market_data"])
        return (
            [SimpleNamespace(entry=datetime(2024, 1, 1))],
            [(datetime(2024, 1, 1), 1.0)],
            [],
        )

    monkeypatch.setattr(cli, "run_backtest", run_backtest)
    monkeypatch.setattr(cli, "finalize_run", lambda *a, **k: state.update(k))

    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text("{}")

    ns = Namespace(demo=False, user="user", config=str(cfg_path))
    assert cli.cmd_run_backtest(ns) == 0
    assert state["market_len"] == 6  # No filtering without fast_mode
    assert state["params"] == {"length": 1}
    assert compiled_cfg["features"][0]["params"]["length"] == 2


def test_cmd_run_backtest_rmm_constant_modes(cli_stubs, tmp_path, monkeypatch):
    cli, _, _ = cli_stubs

    class FlatRMM:
        def __init__(self, config: Any) -> None:
            # Accept either dict or Pydantic model for testing flexibility
            self.config = config

        def classify_daily(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {"label": ["flat"], "confidence": [0.5]},
                index=[df.index[0]],
            )

        def project_to_index(self, daily, index, policy):
            values = list(index)
            if values:
                values[0] = None
            flat_modes: list[list[str]] = []
            for idx, ts in enumerate(index):
                if idx == 0:
                    flat_modes.append(["long"])
                elif idx == 1:
                    flat_modes.append(["short"])
                else:
                    flat_modes.append(["short"])
            return pd.DataFrame(
                {
                    "label": ["flat"] * len(index),
                    "confidence": [0.5] * len(index),
                    "allowed_sides": flat_modes,
                },
                index=pd.Index(values, dtype=object),
            )

    monkeypatch.setattr(cli, "RMMEngine", FlatRMM)
    cfg = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "rmm_config": {
            "regimes": [
                {
                    "label": "flat",
                    "confidence": 0.5,
                    "conditions": {
                        "all_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    },
                }
            ]
        },
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
        },
    }
    cfg_path = tmp_path / "cfg_rmm_constant.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="user", config=str(cfg_path))

    assert cli.cmd_run_backtest(ns) == 0


def test_cmd_run_backtest_rmm_empty_projection(cli_stubs, tmp_path, monkeypatch):
    cli, _, _ = cli_stubs

    class EmptyRMM:
        def __init__(self, config: Any) -> None:
            # Accept either dict or Pydantic model for testing flexibility
            self.config = config

        def classify_daily(self, df: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame(
                {"label": [], "confidence": []},
                index=pd.DatetimeIndex([]),
            )

        def project_to_index(self, daily, index, policy):
            return pd.DataFrame(
                columns=["label", "confidence", "allowed_sides"],
                index=index[:0],
            )

    monkeypatch.setattr(cli, "RMMEngine", EmptyRMM)
    cfg = {
        "run_id": "rid",
        "data_request": {"symbol": "EURUSD"},
        "rmm_config": {
            "regimes": [
                {
                    "label": "empty",
                    "confidence": 0.5,
                    "conditions": {
                        "all_of": [
                            {"condition": "is_above", "left": "close", "right": 1.0}
                        ]
                    },
                }
            ]
        },
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [{"any_of": []}],
            "long_exit_rules": [{"any_of": []}],
        },
    }
    cfg_path = tmp_path / "cfg_rmm_empty.json"
    cfg_path.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="user", config=str(cfg_path))

    assert cli.cmd_run_backtest(ns) == 0


def test_cmd_ai_diagnose_train_and_qualitative(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"meta": {"id": "x"}}))

    class DummyEngine:
        def __init__(self, analysis_data: dict[str, Any]) -> None:
            self.analysis_data = analysis_data

        def run(self) -> None:
            pass

        def generate_report_markdown(self) -> str:
            return "# report"

        def generate_report_json(self) -> str:
            return "{}"

    monkeypatch.setattr(cli, "DiagnosticSynthesisEngine", DummyEngine)

    monkeypatch.setattr(
        "trading_platform.ai.lab.trainer.train_profitability_model",
        lambda data: ("model", ["f1"]),
    )
    saved: dict[str, str] = {}

    def save_model(model: object, path: str) -> None:
        saved["path"] = path

    monkeypatch.setattr(
        "trading_platform.ai.lab.trainer.save_model",
        save_model,
    )

    class DummyClient:
        pass

    class DummyLLMEngine:
        def __init__(self, brief_data: dict[str, Any], client: DummyClient) -> None:
            self.brief_data = brief_data
            self.client = client

        def run(self) -> str:
            return "feedback"

    monkeypatch.setattr(
        "trading_platform.ai.llm_analysis.client.LlmApiClient",
        DummyClient,
    )
    monkeypatch.setattr(
        "trading_platform.ai.llm_analysis.engine.LLMAnalysisEngine",
        DummyLLMEngine,
    )

    ns = Namespace(
        brief=str(brief),
        train_model=True,
        qualitative_report=True,
    )

    assert cli.cmd_ai_diagnose(ns) == 0
    assert (brief.parent / "ai_diagnostic_report.md").exists()
    assert saved["path"].endswith("profitability_model.joblib")


def test_cmd_ai_diagnose_qualitative_failure(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"meta": {}}))

    class DummyEngine:
        def __init__(self, analysis_data: dict[str, Any]) -> None:
            self.analysis_data = analysis_data

        def run(self) -> None:
            pass

        def generate_report_markdown(self) -> str:
            return "md"

        def generate_report_json(self) -> str:
            return "{}"

    monkeypatch.setattr(cli, "DiagnosticSynthesisEngine", DummyEngine)
    monkeypatch.setattr(
        "trading_platform.ai.llm_analysis.client.LlmApiClient",
        lambda: object(),
    )

    class FailingEngine:
        def __init__(self, brief_data: dict[str, Any], client: object) -> None:
            self.brief_data = brief_data
            self.client = client

        def run(self) -> str:
            raise RuntimeError("fail")

    monkeypatch.setattr(
        "trading_platform.ai.llm_analysis.engine.LLMAnalysisEngine",
        FailingEngine,
    )

    ns = Namespace(brief=str(brief), qualitative_report=True, train_model=False)
    assert cli.cmd_ai_diagnose(ns) == 0


def test_cmd_run_live_dry_run():
    import trading_platform.cli as cli

    ns = Namespace(dry_run=True, config=None)
    assert cli.cmd_run_live(ns) == 0


def test_cmd_run_live_full(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    cfg_path = tmp_path / "live.json"
    cfg_path.write_text("{}")

    monkeypatch.setattr(
        cli,
        "_load_config",
        lambda path: {"initial_cash": 5000, "pm_limits": {"max": 1}},
    )

    class DummyRunConfig:
        @staticmethod
        def model_validate(data: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(blackout_utc=[], blackout_events=[])

    monkeypatch.setattr(cli, "RunConfig", DummyRunConfig)

    class DummyPolicy:
        @staticmethod
        def from_config(**kwargs) -> SimpleNamespace:
            return SimpleNamespace(policy=True)

    monkeypatch.setattr(cli, "TradingWindowPolicy", DummyPolicy)

    class DummyPM:
        def __init__(self, base_currency: str, initial_cash: float) -> None:
            self.base_currency = base_currency
            self.initial_cash = initial_cash

    monkeypatch.setattr(cli, "PortfolioManager", DummyPM)

    state: dict[str, bool] = {}

    class DummyAdapter:
        def __init__(
            self,
            pm: DummyPM,
            policy: SimpleNamespace,
            pm_limits=None,
        ) -> None:
            self.pm = pm
            self.policy = policy
            self.pm_limits = pm_limits

        def connect(self) -> None:
            state["connect"] = True

        def shutdown(self) -> None:
            state["shutdown"] = True

    monkeypatch.setattr(cli, "OandaStubAdapter", DummyAdapter)

    ns = Namespace(dry_run=False, config=str(cfg_path))
    assert cli.cmd_run_live(ns) == 0
    assert state == {"connect": True, "shutdown": True}


def test_find_last_briefs_missing_dir(tmp_path):
    import trading_platform.cli as cli

    missing = tmp_path / "missing"
    assert cli._find_last_briefs(missing, None, 3) == []


def test_find_last_briefs_sorted(tmp_path):
    import trading_platform.cli as cli

    runs = tmp_path / "runs"
    runs.mkdir()
    paths: list[Path] = []
    for name in ["a", "b", "c"]:
        run_dir = runs / name
        run_dir.mkdir()
        brief = run_dir / "brief.json"
        brief.write_text("{}")
        timestamp = os.path.getmtime(brief) + float(len(paths))
        os.utime(brief, (timestamp, timestamp))
        paths.append(brief)

    latest = cli._find_last_briefs(runs, None, 2)
    assert [p.parent.name for p in latest] == ["c", "b"]


def test_find_last_briefs_skips_non_briefs(tmp_path):
    import trading_platform.cli as cli

    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "not_a_dir.txt").write_text("x")
    empty_dir = runs / "empty"
    empty_dir.mkdir()
    result = cli._find_last_briefs(runs, None, 2)
    assert result == []


def test_cmd_compare_last_branch(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    runs_dir = tmp_path / "runs"
    user_dir = runs_dir / "user"
    user_dir.mkdir(parents=True)
    briefs = []
    for idx in range(3):
        run_dir = user_dir / f"run_{idx}"
        run_dir.mkdir()
        brief = run_dir / "brief.json"
        brief.write_text(json.dumps({"meta": {"run_id": f"r{idx}"}}))
        briefs.append(brief)

    monkeypatch.setattr(cli, "_find_last_briefs", lambda *_: briefs)
    written: list[Path] = []

    def save_report(a: Path, b: Path, out: Path) -> None:
        out.write_text("ok")
        written.append(out)

    monkeypatch.setattr(cli, "save_comparison_report", save_report)

    ns = Namespace(
        last=3,
        runs_dir=str(runs_dir),
        user="user",
        a=None,
        b=None,
        out="ignored.html",
    )

    assert cli.cmd_compare(ns) == 0
    assert len(written) == 2


def test_cmd_compare_last_not_enough(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    monkeypatch.setattr(cli, "_find_last_briefs", lambda *_: [tmp_path / "one.json"])
    ns = Namespace(
        last=2,
        runs_dir=str(tmp_path),
        user=None,
        a=None,
        b=None,
        out="ignored.html",
    )
    assert cli.cmd_compare(ns) == 2


def test_cmd_open_chart_generates_and_opens(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "user" / "run1"
    run_dir.mkdir(parents=True)
    brief = run_dir / "brief.json"
    brief.write_text(json.dumps({"meta": {"run_id": "run1"}}))

    def save_chart(path: Path) -> None:
        (path / "chart.html").write_text("<html></html>")

    monkeypatch.setattr(cli, "save_chart_from_brief", save_chart)
    opened: dict[str, str] = {}
    monkeypatch.setattr(
        "webbrowser.open",
        lambda url: opened.setdefault("url", url),
    )

    ns = Namespace(
        runs_dir=str(runs_dir),
        user="user",
        last=1,
        open=True,
    )

    assert cli.cmd_open_chart(ns) == 0
    assert opened["url"].startswith("file:")


def test_cmd_open_chart_open_failure(tmp_path, monkeypatch):
    import trading_platform.cli as cli

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "user" / "run2"
    run_dir.mkdir(parents=True)
    brief = run_dir / "brief.json"
    brief.write_text(json.dumps({"meta": {"run_id": "run2"}}))
    chart = run_dir / "chart.html"
    chart.write_text("<html></html>")

    monkeypatch.setattr(cli, "save_chart_from_brief", lambda path: None)
    monkeypatch.setattr(
        "webbrowser.open",
        lambda url: (_ for _ in ()).throw(RuntimeError("open fail")),
    )

    ns = Namespace(
        runs_dir=str(runs_dir),
        user="user",
        last=1,
        open=True,
    )

    assert cli.cmd_open_chart(ns) == 0

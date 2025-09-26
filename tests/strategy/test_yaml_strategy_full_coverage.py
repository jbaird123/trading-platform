from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from trading_platform.strategy import yaml_strategy as ys


def _base_config() -> dict[str, Any]:
    return {
        "strategy_name": "Test",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
    }


def test_validate_strategy_config_jsonschema_failure(monkeypatch):
    cfg = _base_config()

    class DummyValidationError(Exception):
        def __init__(self, msg: str) -> None:
            super().__init__(msg)
            self.message = msg

    def fake_validate(config: dict[str, Any], schema: dict[str, Any]) -> None:
        raise DummyValidationError("bad field")

    fake_jsonschema = SimpleNamespace(
        validate=fake_validate, ValidationError=DummyValidationError
    )
    monkeypatch.setattr(ys, "jsonschema", fake_jsonschema)

    with pytest.raises(ValueError, match="bad field"):
        ys.validate_strategy_config(cfg)


def test_validate_strategy_config_without_jsonschema(monkeypatch):
    cfg = _base_config()
    monkeypatch.setattr(ys, "jsonschema", None)
    ys.validate_strategy_config(cfg)


def test_validate_strategy_config_invalid_type():
    with pytest.raises(ValueError, match="strategy must be an object"):
        ys.validate_strategy_config([])  # type: ignore[arg-type]


def test_load_strategy_config_from_path(tmp_path):
    cfg = {"strategy_name": "FileStrategy"}
    file_path = tmp_path / "cfg.json"
    file_path.write_text(json.dumps(cfg))
    loaded = ys.load_strategy_config(file_path)
    assert loaded == cfg


def test_series_for_operand_variants():
    df = pd.DataFrame({"close": [1, 2], "feat": [3, 4]})
    assert list(ys._series_for_operand(df, 5.0)) == [5.0, 5.0]
    assert list(ys._series_for_operand(df, "close")) == [1.0, 2.0]
    assert list(ys._series_for_operand(df, {"ref": "feat"})) == [3.0, 4.0]
    assert list(ys._series_for_operand(df, {"bad": 1})) == [0.0, 0.0]


def test_eval_predicate_all_conditions():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]})
    above = ys._eval_predicate(df, {"condition": "is_above", "left": "b", "right": "a"})
    below = ys._eval_predicate(df, {"condition": "is_below", "left": "a", "right": "b"})
    cross_up = ys._eval_predicate(
        df, {"condition": "cross_above", "left": "a", "right": "b"}
    )
    cross_down = ys._eval_predicate(
        df, {"condition": "cross_below", "left": "b", "right": "a"}
    )
    default = ys._eval_predicate(df, {"condition": "unknown"})
    assert list(above) == [True, False, False]
    assert list(below) == [True, False, False]
    assert list(cross_up) == [False, False, True]
    assert list(cross_down) == [False, False, True]
    assert not default.any()


def test_eval_rule_block_branches():
    df = pd.DataFrame({"x": [2, 3, 4], "y": [0, 1, 2]})
    all_block = {"all_of": [{"condition": "is_above", "left": "x", "right": "y"}]}
    any_block = {"any_of": [{"condition": "is_below", "left": "y", "right": "x"}]}
    none_block = {}
    assert ys._eval_rule_block(df, all_block).all()
    assert ys._eval_rule_block(df, any_block).iloc[0]
    assert not ys._eval_rule_block(df, none_block).any()


class DummyAIClient:
    def __init__(self, responses: list[dict[str, Any]] | Exception):
        self._responses = responses
        self.calls = 0

    def predict(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        self.calls += 1
        if isinstance(self._responses, Exception):
            raise self._responses
        return self._responses


def _patch_features(monkeypatch, frame: pd.DataFrame) -> None:
    monkeypatch.setattr(
        ys,
        "compute_features",
        lambda df, f, p: frame.copy(),
    )


def test_compiled_strategy_generate_signals_basic(monkeypatch):
    base = pd.DataFrame({"close": [1, 2, 1], "feat": [0, 1, 0]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="basic",
        overlays=[],
        features=[{"name": "feat"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        long_exit_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 1.5}]}
        ],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["flat", "long", "flat"]
    assert strat.get_context(1) == {"feat": 1}
    assert strat.get_context(10) == {}


def test_compiled_strategy_slope_and_ai_filter(monkeypatch):
    base = pd.DataFrame(
        {
            "close": [1.0, 2.0, 3.0, 4.0],
            "ema_slow": [1.0, 1.1, 1.2, 1.3],
            "fast": [0.0, 1.0, 0.0, 1.0],
        }
    )
    _patch_features(monkeypatch, base)
    predictions = [
        {"prediction": "long", "confidence": 0.8},
        {"prediction": "long", "confidence": 0.2},
        {"prediction": "short", "confidence": 0.9},
        {"prediction": "flat", "confidence": 0.9},
    ]
    ai_client = DummyAIClient(predictions)
    strat = ys.CompiledStrategy(
        name="ai",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
        ],
        long_exit_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 3.5}]}
        ],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 3.5}]}
        ],
        short_exit_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 3.5}]}
        ],
        parameters={"slope_filter": True, "slope_feature": "ema_slow"},
        slope_filter=True,
        slope_feature="ema_slow",
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=[],
    )
    sig = strat.generate_signals(base)
    values = list(sig)
    assert ai_client.calls == 1
    assert len(values) == 4
    assert set(values).issubset({"flat", "long", "short"})


def test_compiled_strategy_ai_filter_missing_features(monkeypatch, caplog):
    base = pd.DataFrame({"close": [1, 2], "fast": [1, 1]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="missing-ai",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["missing"],
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["long", "long"]
    assert "Missing AI input features" in caplog.text


def test_compiled_strategy_ai_filter_exception(monkeypatch, caplog):
    base = pd.DataFrame({"close": [1, 2]})
    _patch_features(monkeypatch, base)
    strat = ys.CompiledStrategy(
        name="ai-error",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient(Exception("boom")),
        ai_confidence_threshold=0.5,
    )
    sig = strat.generate_signals(base)
    assert list(sig) == ["long", "long"]
    assert "Error during AI inference" in caplog.text


def test_compiled_strategy_ai_filter_with_inputs(monkeypatch):
    base = pd.DataFrame({"close": [1, 2], "fast": [0.5, 0.6]})
    _patch_features(monkeypatch, base)
    ai_client = DummyAIClient(
        [
            {"prediction": "long", "confidence": 0.9},
            {"prediction": "flat", "confidence": 0.9},
        ]
    )
    strat = ys.CompiledStrategy(
        name="ai-inputs",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    sig = strat.generate_signals(base)
    assert ai_client.calls == 1
    assert list(sig) == ["long", "long"]


def test_compile_strategy_ai_enabled(monkeypatch):
    cfg = {
        "strategy_name": "compile",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
        "features": [],
        "parameters": {"slope_filter": True, "slope_feature": "custom"},
        "ai_filter": {
            "enabled": True,
            "confidence_threshold": 0.3,
            "input_features": ["fast"],
        },
    }

    class DummyValidationError(Exception):
        pass

    fake_jsonschema = SimpleNamespace(
        validate=lambda cfg, schema: None,
        ValidationError=DummyValidationError,
    )
    monkeypatch.setattr(ys, "jsonschema", fake_jsonschema)
    strat = ys.compile_strategy(cfg)
    assert strat.slope_filter is True
    assert strat.slope_feature == "custom"
    assert strat.ai_filter_enabled is True
    assert strat.ai_inference_client is not None


def test_compile_strategy_ai_disabled_without_jsonschema(monkeypatch):
    cfg = {
        "strategy_name": "no-ai",
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": 1, "right": 0}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": 1, "right": 2}]}
        ],
        "ai_filter": {"enabled": True},
        "parameters": "not-a-dict",
    }
    monkeypatch.setattr(ys, "jsonschema", None)
    strat = ys.compile_strategy(cfg)
    assert strat.ai_filter_enabled is False
    assert strat.parameters == {}


def test_reload_without_jsonschema(monkeypatch):
    import builtins
    import importlib

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "jsonschema":
            raise ImportError
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    module = importlib.reload(ys)
    assert module.jsonschema is None
    monkeypatch.setattr(builtins, "__import__", original_import)
    module = importlib.reload(module)
    globals()["ys"] = module
    target = globals()["ys"]

    df = pd.DataFrame({"close": [0.0, 0.2, 1.0], "fast": [1.0, 1.5, 2.0]})
    monkeypatch.setattr(
        target,
        "compute_features",
        lambda frame, feats, params: df.copy(),
    )
    ai_client = DummyAIClient(
        [
            {"prediction": "short", "confidence": 0.9},
            {"prediction": "short", "confidence": 0.9},
            {"prediction": "flat", "confidence": 0.9},
        ]
    )
    strat = target.CompiledStrategy(
        name="reload",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
        short_exit_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
        ],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=ai_client,
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    strat.generate_signals(df)
    target._series_for_operand(df, "fast")
    target._series_for_operand(df, "missing")
    no_ai = target.CompiledStrategy(
        name="branch-no-ai",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    no_ai.generate_signals(df)
    half_ai = target.CompiledStrategy(
        name="branch-half",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=None,
    )
    half_ai.generate_signals(df)

    empty_ai = target.CompiledStrategy(
        name="branch-empty",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": -1}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["fast"],
    )
    empty_ai.generate_signals(df)

    missing_ai = target.CompiledStrategy(
        name="branch-missing",
        overlays=[],
        features=[{"name": "fast"}],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": "close", "right": -1}]}
        ],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
        ai_filter_enabled=True,
        ai_inference_client=DummyAIClient([]),
        ai_confidence_threshold=0.5,
        ai_input_features=["missing"],
    )
    missing_ai.generate_signals(df)


def test_load_strategy_config_returns_dict():
    cfg = {"name": "inline"}
    out = ys.load_strategy_config(cfg)
    assert out is cfg

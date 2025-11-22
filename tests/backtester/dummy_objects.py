from __future__ import annotations

from typing import Any, cast

from trading_platform.strategy.models import StrategyConfig
from trading_platform.strategy.yaml_strategy import (
    CompiledStrategy,
    validate_strategy_config,
)


def _base_config(name: str) -> dict:
    cfg: dict[str, Any] = {
        "strategy_name": name,
        "features": [],
        "overlays": [],
        "parameters": {},
        "long_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        "long_exit_rules": [],
        "short_entry_rules": [],
        "short_exit_rules": [],
    }
    validate_strategy_config(cfg)
    validated = StrategyConfig.model_validate(cast(dict[str, Any], cfg))
    return validated.model_dump(exclude_none=True)


def _dummy_strategy_cfg() -> CompiledStrategy:
    """Returns a minimal, validated CompiledStrategy for testing."""
    strat = CompiledStrategy(
        name="dummy",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    object.__setattr__(strat, "original_config", _base_config("dummy"))
    return strat


def _dummy_strategy_with_tp(tp_price: float) -> CompiledStrategy:
    """Returns a dummy strategy with a take-profit rule."""
    strat = CompiledStrategy(
        name="dummy_tp",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        long_exit_blocks=[{"take_profit": {"value": tp_price, "type": "price"}}],
        short_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        short_exit_blocks=[{"take_profit": {"value": tp_price, "type": "price"}}],
        parameters={},
    )
    object.__setattr__(strat, "original_config", _base_config("dummy_tp"))
    return strat


def _dummy_strategy_with_sl(sl_price: float) -> CompiledStrategy:
    """Returns a dummy strategy with a stop-loss rule."""
    strat = CompiledStrategy(
        name="dummy_sl",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        long_exit_blocks=[{"stop_loss": {"value": sl_price, "type": "price"}}],
        short_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        short_exit_blocks=[{"stop_loss": {"value": sl_price, "type": "price"}}],
        parameters={},
    )
    object.__setattr__(strat, "original_config", _base_config("dummy_sl"))
    return strat


def _dummy_strategy_with_sl_tp(sl: float, tp: float) -> CompiledStrategy:
    """Returns a dummy strategy with stop-loss and take-profit rules."""
    strat = CompiledStrategy(
        name="dummy_sl_tp",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        long_exit_blocks=[
            {"stop_loss": {"value": sl, "type": "price"}},
            {"take_profit": {"value": tp, "type": "price"}},
        ],
        short_entry_blocks=[
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"value": 1},
                        "right": {"value": 0},
                    }
                ]
            }
        ],
        short_exit_blocks=[
            {"stop_loss": {"value": sl, "type": "price"}},
            {"take_profit": {"value": tp, "type": "price"}},
        ],
        parameters={},
    )
    object.__setattr__(strat, "original_config", _base_config("dummy_sl_tp"))
    return strat

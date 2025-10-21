from __future__ import annotations

from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy_cfg() -> CompiledStrategy:
    """Returns a minimal, empty CompiledStrategy for testing."""
    return CompiledStrategy(
        name="dummy",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def _dummy_strategy_with_tp(tp_price: float) -> CompiledStrategy:
    """Returns a dummy strategy with a take-profit rule."""
    return CompiledStrategy(
        name="dummy_tp",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        long_exit_blocks=[{"take_profit": {"value": tp_price, "type": "price"}}],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        short_exit_blocks=[{"take_profit": {"value": tp_price, "type": "price"}}],
        parameters={},
    )


def _dummy_strategy_with_sl(sl_price: float) -> CompiledStrategy:
    """Returns a dummy strategy with a stop-loss rule."""
    return CompiledStrategy(
        name="dummy_sl",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        long_exit_blocks=[{"stop_loss": {"value": sl_price, "type": "price"}}],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        short_exit_blocks=[{"stop_loss": {"value": sl_price, "type": "price"}}],
        parameters={},
    )


def _dummy_strategy_with_sl_tp(sl: float, tp: float) -> CompiledStrategy:
    """Returns a dummy strategy with stop-loss and take-profit rules."""
    return CompiledStrategy(
        name="dummy_sl_tp",
        overlays=[],
        features=[],
        long_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        long_exit_blocks=[
            {"stop_loss": {"value": sl, "type": "price"}},
            {"take_profit": {"value": tp, "type": "price"}},
        ],
        short_entry_blocks=[
            {"any_of": [{"condition": "is_above", "left": {"value": 1}, "right": {"value": 0}}]}
        ],
        short_exit_blocks=[
            {"stop_loss": {"value": sl, "type": "price"}},
            {"take_profit": {"value": tp, "type": "price"}},
        ],
        parameters={},
    )

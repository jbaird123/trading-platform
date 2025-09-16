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
        risk={},
    )

# Validates: [BT-7.7], [SYS-1.1.2], [SYS-1.7.3]
from __future__ import annotations

from trading_platform.core.config import RunConfig


def test_runconfig_has_warmup_bars_field():
    cfg = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        instrument={"symbol": "EURUSD"},
    )
    assert hasattr(cfg, "warmup_bars")
    assert isinstance(cfg.warmup_bars, int)
    cfg2 = RunConfig(
        user_id="test",
        run_seed=42,
        log_level="INFO",
        initial_cash=1000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        execution_model="next_bar_open",
        exit_tie_break="stop_then_tp",
        instrument={"symbol": "EURUSD"},
        warmup_bars=5,
    )
    assert cfg2.warmup_bars == 5

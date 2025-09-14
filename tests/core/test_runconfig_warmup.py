from __future__ import annotations

from trading_platform.core.config import RunConfig


def test_runconfig_has_warmup_bars_field():
    cfg = RunConfig()
    assert hasattr(cfg, "warmup_bars")
    assert isinstance(cfg.warmup_bars, int)
    cfg2 = RunConfig(warmup_bars=5)
    assert cfg2.warmup_bars == 5

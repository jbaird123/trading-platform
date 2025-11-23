from __future__ import annotations

from trading_platform.core.research_profiles import make_research_config


def test_make_research_config_creates_minimal_sections():
    cfg = make_research_config(
        strategy_path="config/strategy/ema_crossover.yaml",
        symbol="EURUSD",
        timeframe="1H",
        start="2023-01-01",
        end="2023-03-01",
        grid={"ema_fast_length": [8, 12], "ema_slow_length": [50, 100]},
    )
    assert cfg["parameter_search"]["grid"]["ema_fast_length"] == [8, 12]
    assert cfg["walk_forward"]["window"] > 0
    assert cfg["monte_carlo"]["trials"] > 0

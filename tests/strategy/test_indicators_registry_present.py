from __future__ import annotations

from trading_platform.strategy.indicators_registry import INDICATORS


def test_indicators_registry_has_bb_and_bbwidth():
    assert "BB" in INDICATORS and "BBWidth" in INDICATORS

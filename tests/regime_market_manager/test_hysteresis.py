"""Tests for RMM hysteresis functionality.

# Validates: [RMM-4.7]
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.regime_market_manager.models import (
    RMMConfig,
    RMMHysteresis,
    RMMPredicate,
    RMMRegime,
    RMMRuleBlock,
)


def _make_engine(min_bars: int, cooldown: int) -> RMMEngine:
    """Build a simple RMM engine for hysteresis tests."""
    hysteresis = RMMHysteresis(
        min_bars=min_bars,
        cooldown_bars=cooldown,
    )

    config = RMMConfig(
        timeframe="1H",
        hysteresis=hysteresis,
        regimes=[
            RMMRegime(
                label="trend_high",
                confidence=0.8,
                conditions=RMMRuleBlock(
                    all_of=[
                        RMMPredicate(
                            condition="is_above",
                            left={"ref": "trend_strength"},
                            right=0.5,
                        )
                    ]
                ),
            ),
            RMMRegime(
                label="trend_low",
                confidence=0.6,
                conditions=RMMRuleBlock(
                    all_of=[
                        RMMPredicate(
                            condition="is_below",
                            left={"ref": "trend_strength"},
                            right=0.5,
                        )
                    ]
                ),
            ),
        ],
    )
    return RMMEngine(config)


def _make_frame(values: Iterable[float]) -> pd.DataFrame:
    """Create an OHLCV frame with a synthetic trend strength column."""
    vals = list(values)
    size = len(vals)
    index = pd.date_range("2024-01-01", periods=size, freq="1h")
    data = {
        "open": [1.0] * size,
        "high": [1.0] * size,
        "low": [1.0] * size,
        "close": [1.0] * size,
        "volume": [0.0] * size,
        "trend_strength": vals,
    }
    return pd.DataFrame(data, index=index)


def test_hysteresis_disabled_matches_raw_series() -> None:
    engine = _make_engine(min_bars=0, cooldown=0)
    df = _make_frame([0.7, 0.2, 0.8, 0.3])
    result = engine.classify_regime(
        df, timeframe="1H", already_resampled=True
    )

    assert result["label"].tolist() == result["raw_label"].tolist()
    assert result["confidence"].tolist() == result["raw_confidence"].tolist()


def test_min_bars_delays_first_switch() -> None:
    engine = _make_engine(min_bars=2, cooldown=0)
    df = _make_frame([0.7, 0.65, 0.3, 0.2, 0.2])
    result = engine.classify_regime(
        df, timeframe="1H", already_resampled=True
    )

    assert result["raw_label"].tolist() == [
        "trend_high",
        "trend_high",
        "trend_low",
        "trend_low",
        "trend_low",
    ]
    assert result["label"].tolist() == [
        "trend_high",
        "trend_high",
        "trend_high",
        "trend_low",
        "trend_low",
    ]
    assert result["bars_in_state"].tolist() == [0, 1, 2, 0, 1]


def test_cooldown_blocks_immediate_flip() -> None:
    engine = _make_engine(min_bars=0, cooldown=2)
    df = _make_frame([0.7, 0.3, 0.3, 0.7, 0.7])
    result = engine.classify_regime(
        df, timeframe="1H", already_resampled=True
    )

    assert result["raw_label"].tolist() == [
        "trend_high",
        "trend_low",
        "trend_low",
        "trend_high",
        "trend_high",
    ]
    assert result["label"].tolist() == [
        "trend_high",
        "trend_low",
        "trend_low",
        "trend_low",
        "trend_high",
    ]
    assert result["cooldown_remaining"].tolist() == [0, 2, 1, 0, 2]

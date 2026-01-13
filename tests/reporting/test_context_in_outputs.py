"""Task 30: Test that new contextual features appear in brief.json and trades.csv.

This test verifies that:
1. Trade.context_at_entry captures new slope-based and RMM features
2. These features appear in brief.json trades array
3. These features appear in trades.csv output
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief
from trading_platform.reporting.csv_export import save_trades_csv


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_trade_context_includes_new_features_in_brief() -> None:
    """Task 30: Verify new features in Trade.context_at_entry appear in brief.json."""

    # Create a trade with context including new features from Epics 1-3
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0, 0),
        exit_time=datetime(2024, 1, 1, 11, 0, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000.0,
        pnl=500.0,
        pnl_movement=500.0,
        exit_reason="take_profit",
        context_at_entry={
            "strategy_features": {
                "ema_fast": 1.0985,
                "ema_slope_fast": 0.0012,  # Epic 1: new EMASlope feature
                "adx_4h_ADX": 28.5,  # Epic 1: higher-timeframe feature (ADX main value)
                "adx_4h_DI+": 25.0,  # ADX directional indicator
                "adx_4h_DI-": 20.0,  # ADX directional indicator
            },
            "global_features": {
                "volume": 50000.0,  # Market context
            },
            "regime": {
                "label": "trending",
                "confidence": 0.85,
                "atr_pct": 75.3,  # Epic 3: new ATRPercentile feature
                "rvol": 0.0145,  # Epic 3: new RealizedVolatility feature
                "vol_z": 1.2,  # Epic 3: new VolumeZScore feature
            },
        },
    )

    # Generate brief
    brief_data = generate_brief(
        meta={"run_id": "test-context"},
        params={},
        trades=[trade],
        initial_cash=10000,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )

    # Verify brief contains trades with context
    assert "trades" in brief_data
    assert len(brief_data["trades"]) == 1

    trade_in_brief = brief_data["trades"][0]

    # Verify context_at_entry is in the serialized trade
    assert "context_at_entry" in trade_in_brief

    context = trade_in_brief["context_at_entry"]

    # Verify Epic 1 features: EMASlope and higher-timeframe
    assert "strategy_features" in context
    assert context["strategy_features"]["ema_slope_fast"] == 0.0012
    # ADX now returns 3 columns, check the main ADX value
    assert context["strategy_features"]["adx_4h_ADX"] == 28.5

    # Verify Epic 3 features: new RMM features
    assert "regime" in context
    regime_ctx = context["regime"]
    assert regime_ctx["atr_pct"] == 75.3
    assert regime_ctx["rvol"] == 0.0145
    assert regime_ctx["vol_z"] == 1.2
    assert regime_ctx["raw_label"] == "trending"
    assert regime_ctx["raw_confidence"] == 0.85
    assert regime_ctx["allowed_sides"] == []
    assert regime_ctx["bars_in_state"] == 0
    assert regime_ctx["cooldown_remaining"] == 0
    assert regime_ctx["hysteresis"]["bars_in_state"] == 0
    assert regime_ctx["hysteresis"]["cooldown_remaining"] == 0


def test_trade_context_includes_new_features_in_csv(tmp_path: Path) -> None:
    """Task 30: Verify new features in Trade.context_at_entry appear in trades.csv."""

    # Create a trade with context including new features
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0, 0),
        exit_time=datetime(2024, 1, 1, 11, 0, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000.0,
        pnl=500.0,
        pnl_movement=500.0,
        exit_reason="take_profit",
        context_at_entry={
            "strategy_features": {
                "ema_fast": 1.0985,
                "ema_slope_fast": 0.0012,  # Epic 1: new feature
                "adx_4h_ADX": 28.5,  # Epic 1: higher-timeframe (ADX main value)
                "adx_4h_DI+": 25.0,  # ADX directional indicator
                "adx_4h_DI-": 20.0,  # ADX directional indicator
            },
            "global_features": {
                "volume": 50000.0,  # Market context
            },
            "regime": {
                "label": "trending",
                "confidence": 0.85,
                "atr_pct": 75.3,  # Epic 3: new feature
                "rvol": 0.0145,  # Epic 3: new feature
                "vol_z": 1.2,  # Epic 3: new feature
            },
        },
    )

    # Save to CSV
    csv_path = tmp_path / "trades.csv"
    save_trades_csv(csv_path, [trade])

    # Read CSV and verify context fields are present
    df = pd.read_csv(csv_path)

    assert len(df) == 1

    # Verify context columns exist and have correct values
    # Epic 1 features (nested under strategy_features)
    assert "ctx_strategy_features_ema_slope_fast" in df.columns
    assert df.iloc[0]["ctx_strategy_features_ema_slope_fast"] == 0.0012

    # ADX now has 3 columns, check the main ADX value
    assert "ctx_strategy_features_adx_4h_ADX" in df.columns
    assert df.iloc[0]["ctx_strategy_features_adx_4h_ADX"] == 28.5

    # Epic 3 features (directly under regime)
    assert "ctx_regime_atr_pct" in df.columns
    assert df.iloc[0]["ctx_regime_atr_pct"] == 75.3

    assert "ctx_regime_rvol" in df.columns
    assert df.iloc[0]["ctx_regime_rvol"] == 0.0145

    assert "ctx_regime_vol_z" in df.columns
    assert df.iloc[0]["ctx_regime_vol_z"] == 1.2

    assert "ctx_regime_raw_label" in df.columns
    assert df.iloc[0]["ctx_regime_raw_label"] == "trending"

    assert "ctx_regime_raw_confidence" in df.columns
    assert df.iloc[0]["ctx_regime_raw_confidence"] == 0.85

    assert "ctx_regime_allowed_sides" in df.columns
    assert df.iloc[0]["ctx_regime_allowed_sides"] == "[]"

    assert "ctx_regime_bars_in_state" in df.columns
    assert df.iloc[0]["ctx_regime_bars_in_state"] == 0

    assert "ctx_regime_cooldown_remaining" in df.columns
    assert df.iloc[0]["ctx_regime_cooldown_remaining"] == 0

    assert "ctx_regime_hysteresis_bars_in_state" in df.columns
    assert df.iloc[0]["ctx_regime_hysteresis_bars_in_state"] == 0

    assert "ctx_regime_hysteresis_cooldown_remaining" in df.columns
    assert df.iloc[0]["ctx_regime_hysteresis_cooldown_remaining"] == 0


def test_context_at_entry_defaults_to_none_when_missing() -> None:
    """Test that trades without context don't break serialization."""

    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0, 0),
        exit_time=datetime(2024, 1, 1, 11, 0, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000.0,
        pnl=500.0,
        pnl_movement=500.0,
        # No context_at_entry provided
    )

    brief_data = generate_brief(
        meta={"run_id": "test-no-context"},
        params={},
        trades=[trade],
        initial_cash=10000,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )

    # Should still work, just with None or empty context
    trade_in_brief = brief_data["trades"][0]
    # context_at_entry should be None or not present
    assert trade_in_brief.get("context_at_entry") is None

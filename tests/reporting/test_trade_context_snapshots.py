# Validates: [RV-9.7]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_trade_context_snapshots_serialized():
    ctx_entry = {
        "regime": {"label": "trend_up", "confidence": 0.8},
        "indicators": {"ema": 1.23},
    }
    ctx_exit = {
        "regime": {"label": "range", "confidence": 0.5},
        "indicators": {"ema": 1.10},
    }
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.2,
        side="long",
        size=1.0,
        pnl=0.2,
        context_at_entry=ctx_entry,
        context_at_exit=ctx_exit,
    )
    b = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )
    tr = b["trades"][0]
    assert tr["context_at_entry"]["regime"]["label"] == "trend_up"
    assert tr["context_at_exit"]["regime"]["label"] == "range"

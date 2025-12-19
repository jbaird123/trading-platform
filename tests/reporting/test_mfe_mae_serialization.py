# Validates: [JSON-11.25]
from __future__ import annotations

from datetime import datetime, timedelta

from pytest import approx
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_mfe_mae_bars_serialized_in_brief_trades():
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=100.0,
        exit_price=101.0,
        side="long",
        size=10.0,
        pnl=10.0,
        mfe_currency=25.0,
        mae_currency=5.0,
        bars_held=3,
    )
    brief = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )
    tr = brief["trades"][0]
    assert tr["mfe_normalized"] == approx(25.0)
    assert tr["mae_normalized"] == approx(5.0)
    assert tr["bars_held"] == 3

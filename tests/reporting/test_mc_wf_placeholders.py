# Validates: [JSON-F.1], [JSON-F.2]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def _t(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.001,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_brief_includes_mc_and_wf_when_provided():
    brief = generate_brief(
        meta={"run_id": "r1", "strategy_name": "S"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 1.0)],
        initial_cash=1000.0,
        monte_carlo={"seed": 42, "n_paths": 1000},
        walk_forward={
            "splits": [{"train": "2020-01..2020-06", "test": "2020-07..2020-08"}]
        },
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )
    mc = brief.get("monte_carlo")
    wf = brief.get("walk_forward")
    assert mc and mc.get("seed") == 42 and mc.get("n_paths") == 1000
    assert wf and isinstance(wf.get("splits"), list)

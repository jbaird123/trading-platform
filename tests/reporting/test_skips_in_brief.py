# Validates: [JSON-11.26], [JSON-11.27]
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_skipped_trades_and_filter_impact_in_brief():
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1, 1),
        entry_price=1.0,
        exit_price=1.05,
        side="long",
        size=1.0,
        pnl=0.05,
    )
    skips: list[dict[str, Any]] = [
        {
            "entry_time": datetime(2024, 1, 1, 0, 0).isoformat(),
            "symbol": "X",
            "side": "long",
            "size": 1.0,
            "skip_reason": "blackout_static",
            "counterfactual_entry_price": 1.0,
            "counterfactual_pnl": 0.0,
            "policy_snapshot": {"blackout_utc": [("00:00", "01:00")]},
            "notes": None,
        },
        {
            "entry_time": datetime(2024, 1, 1, 2, 0).isoformat(),
            "symbol": "X",
            "side": "long",
            "size": 1.0,
            "skip_reason": "position_cap",
            "counterfactual_entry_price": 1.0,
            "counterfactual_pnl": 0.0,
            "policy_snapshot": {"cap": 1},
            "notes": None,
        },
    ]
    b = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        skipped_trades=skips,
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )
    assert "skipped_trades" in b
    assert b["skipped_trades"] is not None
    assert len(b["skipped_trades"]) == 2
    fi = b.get("filter_impact", {})
    assert fi is not None
    assert fi.get("blackout_static", {}).get("n_skipped") == 1
    assert fi.get("position_cap", {}).get("n_skipped") == 1

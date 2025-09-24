# Validates: [JSON-11.26], [JSON-11.27]
from __future__ import annotations

from datetime import datetime
from typing import Any

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


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
            "timestamp": datetime(2024, 1, 1, 0, 0).isoformat(),
            "symbol": "X",
            "reason_code": "blackout_static",
            "policy_snapshot": {"blackout_utc": [("00:00", "01:00")]},
            "notes": None,
        },
        {
            "timestamp": datetime(2024, 1, 1, 2, 0).isoformat(),
            "symbol": "X",
            "reason_code": "position_cap",
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
    )
    assert "skipped_trades" in b
    assert b["skipped_trades"] is not None
    assert len(b["skipped_trades"]) == 2
    fi = b.get("filter_impact", {})
    assert fi is not None
    assert fi.get("blackout_static", {}).get("n_skipped") == 1
    assert fi.get("position_cap", {}).get("n_skipped") == 1

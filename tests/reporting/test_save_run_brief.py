# Validates: [RV-9.1]
from __future__ import annotations

import json
from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import save_run_brief


def _trade(start: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="TEST",
        entry_time=start,
        exit_time=start + timedelta(days=1),
        entry_price=100.0,
        exit_price=101.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_save_run_brief_writes_json(tmp_path):
    run_path = tmp_path / "user" / "run123"
    trades = [
        _trade(datetime(2023, 1, 1), 100.0),
        _trade(datetime(2023, 1, 2), -50.0),
    ]
    out = save_run_brief(
        run_path,
        meta={"strategy_name": "X", "run_id": "run123"},
        params={"fast": 10, "slow": 20},
        trades=trades,
        initial_cash=1000.0,
    )
    assert out.exists()
    data = json.loads(out.read_text())
    # sanity checks
    assert "overall_performance" in data
    assert "trades" in data and isinstance(data["trades"], list)

from __future__ import annotations

import json
from datetime import datetime, timedelta

from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade


def _trade(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="T",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_finalize_run_writes_brief(tmp_path):
    run_path = tmp_path / "user" / "runA"
    trades = [_trade(datetime(2023, 1, 1, 0), 10.0)]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runA"},
        params={},
        trades=trades,
        initial_cash=1000.0,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert data.get("overall_performance", {}).get("n_trades") == 1

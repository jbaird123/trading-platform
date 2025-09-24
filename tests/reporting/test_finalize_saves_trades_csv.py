# Validates: [RV-9.4]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade


def _t(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0 + (pnl / 10.0),
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        cost_currency=0.01,
        cost_breakdown={"spread": 0.005, "commission": 0.003, "slippage": 0.002},
    )


def test_finalize_run_writes_trades_csv(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        runs_dir=tmp_path,
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
    )
    out = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[_t(datetime(2024, 1, 1), 0.1)],
        initial_cash=1000.0,
        config=cfg,
    )
    # brief.json was written
    assert out.exists()
    # trades.csv was also written
    csv_path = run_path / "trades.csv"
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "symbol,side,size,entry_time,exit_time,entry_price,exit_price" in content

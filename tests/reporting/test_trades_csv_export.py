# Validates: [RV-9.4]
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.csv_export import save_trades_csv


def test_save_trades_csv_writes_expected_columns(tmp_path: Path):
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        r_multiple=1.0,
        mfe_currency=0.2,
        mae_currency=0.05,
        bars_held=3,
        cost_currency=0.01,
        cost_breakdown={"spread": 0.005, "commission": 0.003, "slippage": 0.002},
    )
    out = tmp_path / "runs" / "user" / "id" / "trades.csv"
    p = save_trades_csv(out, [t])
    assert p.exists()
    content = p.read_text()
    # Header contains expected columns
    assert "symbol,side,size,entry_time,exit_time,entry_price,exit_price" in content
    assert (
        ",pnl,r_multiple,mfe_currency,mae_currency,bars_held,cost_currency," in content
    )
    assert ",spread,commission,slippage" in content

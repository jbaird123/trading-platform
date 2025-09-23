# Validates: [RV-9.1], [SYS-1.7.1]
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


def test_finalize_run_model_analysis(tmp_path):
    run_path = tmp_path / "user" / "runB"
    # One TP, one SL, one normal trade
    from datetime import datetime

    from trading_platform.portfolio.trade import Trade

    trades = [
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 1, 0),
            exit_time=datetime(2023, 1, 1, 1),
            entry_price=1.0,
            exit_price=1.2,
            side="long",
            size=1.0,
            pnl=0.2,
            exit_reason="take_profit",
            mfe_currency=0.5,
            mae_currency=0.1,
        ),
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 2, 0),
            exit_time=datetime(2023, 1, 2, 1),
            entry_price=1.0,
            exit_price=0.8,
            side="long",
            size=1.0,
            pnl=-0.2,
            exit_reason="stop_loss",
            mfe_currency=0.1,
            mae_currency=0.4,
        ),
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 3, 0),
            exit_time=datetime(2023, 1, 3, 1),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=1.0,
            pnl=0.1,
            exit_reason="signal",
            mfe_currency=0.2,
            mae_currency=0.05,
        ),
    ]
    from trading_platform.core.run import finalize_run

    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runB"},
        params={},
        trades=trades,
        initial_cash=1000.0,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "model_analysis" in data
    ma = data["model_analysis"]
    assert "avg_pnl_left_on_table_at_tp" in ma
    assert "avg_loss_avoided_by_stop" in ma
    # Check values are as expected
    assert abs(ma["avg_pnl_left_on_table_at_tp"] - (0.5 - 0.2)) < 1e-8
    assert abs(ma["avg_loss_avoided_by_stop"] - (0.4 - 0.2)) < 1e-8


def test_finalize_run_signal_quality_analysis(tmp_path):
    import pandas as pd
    from trading_platform.core.run import finalize_run

    # Create a mock signals.parquet file
    run_path = tmp_path / "user" / "runC"
    run_path.mkdir(parents=True, exist_ok=True)
    signals_path = run_path / "signals.parquet"
    # Simulate a signal series: 3 'long', 2 'flat', 2 'short', 3 'flat', 4 'long'
    sigs = pd.Series(
        ["long"] * 3 + ["flat"] * 2 + ["short"] * 2 + ["flat"] * 3 + ["long"] * 4,
        name="signal",
    )
    sigs.to_frame().to_parquet(signals_path)
    # Minimal trades list
    from datetime import datetime

    from trading_platform.portfolio.trade import Trade

    trades = [
        Trade(
            symbol="T",
            entry_time=datetime(2023, 1, 1, 0),
            exit_time=datetime(2023, 1, 1, 1),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=1.0,
            pnl=0.1,
            exit_reason="signal",
        ),
    ]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "runC"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        signals_path=signals_path,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "signal_quality_analysis" in data
    sqa = data["signal_quality_analysis"]
    assert "signal_persistence_pct" in sqa
    assert "avg_signal_duration_bars" in sqa
    # There are 3+2+4=9 non-flat bars out of 14 total
    assert abs(sqa["signal_persistence_pct"] - (9 / 14 * 100)) < 1e-2
    # Non-flat runs: [3,2,4] => avg = 3.0
    assert abs(sqa["avg_signal_duration_bars"] - 3.0) < 1e-6

import json
from datetime import datetime, timedelta

from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade


def _trade(ts: datetime, pnl: float, regime: str) -> Trade:
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


def test_finalize_run_regimes_section(tmp_path):
    run_path = tmp_path / "user" / "run_regimes"
    # Simulate 3 trades in 2 regimes
    trades = [
        _trade(datetime(2023, 1, 1, 0), 10.0, "bull"),
        _trade(datetime(2023, 1, 2, 0), -5.0, "bear"),
        _trade(datetime(2023, 1, 3, 0), 20.0, "bull"),
    ]
    regimes_at_entry = ["bull", "bear", "bull"]
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "run_regimes"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        regimes_at_entry=regimes_at_entry,
    )
    assert brief_path.exists()
    data = json.loads(brief_path.read_text())
    assert "regimes" in data
    regimes = data["regimes"]
    assert set(regimes.keys()) == {"bull", "bear"}
    # Check bull regime
    bull = regimes["bull"]
    assert bull["n_trades"] == 2
    assert bull["total_pnl"] == 30.0
    assert bull["mean_pnl"] == 15.0
    assert bull["median_pnl"] == 15.0
    assert bull["win_rate"] == 1.0
    # Check bear regime
    bear = regimes["bear"]
    assert bear["n_trades"] == 1
    assert bear["total_pnl"] == -5.0
    assert bear["mean_pnl"] == -5.0
    assert bear["median_pnl"] == -5.0
    assert bear["win_rate"] == 0.0

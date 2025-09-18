# Validates: [RV-9.1]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _make_trade(start: datetime, pnl: float) -> Trade:
    # Simple helper to create a trade with 1-day holding
    exit_time = start + timedelta(days=1)
    side = "long" if pnl >= 0 else "short"
    entry_price = 100.0
    exit_price = entry_price + (pnl / 10000.0)
    return Trade(
        symbol="TEST",
        entry_time=start,
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        side=side,
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_generate_brief_sections_and_types():
    trades = [
        _make_trade(datetime(2023, 1, 1), 100.0),
        _make_trade(datetime(2023, 1, 3), -50.0),
        _make_trade(datetime(2023, 1, 5), 25.0),
    ]
    brief = generate_brief(
        meta={"strategy_name": "TestStrat", "run_id": "abc"},
        params={"fast": 10, "slow": 20},
        trades=trades,
        initial_cash=1000.0,
    )

    # Required top-level sections present
    required_keys = [
        "meta",
        "strategy_params",
        "overall_performance",
        "risk_snapshot",
        "equity_stats",
        "distribution",
        "streaks",
        "holding_time",
        "trades",
    ]
    for k in required_keys:
        assert k in brief

    # Type sanity checks
    assert isinstance(brief["overall_performance"], dict)
    assert isinstance(brief["risk_snapshot"], dict)
    assert isinstance(brief["equity_stats"], dict)
    assert isinstance(brief["distribution"], dict)
    assert isinstance(brief["streaks"], dict)
    assert isinstance(brief["holding_time"], dict)
    assert isinstance(brief["trades"], list)

    # Basic content checks
    op = brief["overall_performance"]
    assert op["n_trades"] == 3
    assert "total_pnl" in op and isinstance(op["total_pnl"], (int, float))
    rs = brief["risk_snapshot"]
    assert "win_rate" in rs and isinstance(rs["win_rate"], (int, float))
    es = brief["equity_stats"]
    assert "equity_curve" in es and isinstance(es["equity_curve"], list)
    dist = brief["distribution"]
    for f in ["pnl_mean", "pnl_median", "pnl_std", "p05", "p95"]:
        assert f in dist


def test_generate_brief_regimes_breakdown():
    trades = [
        _make_trade(datetime(2023, 1, 1), 100.0),
        _make_trade(datetime(2023, 1, 3), -50.0),
        _make_trade(datetime(2023, 1, 5), 25.0),
    ]
    regimes = ["trend_up", "range", "trend_up"]
    brief = generate_brief(
        meta={}, params={}, trades=trades, initial_cash=1000.0, regimes_at_entry=regimes
    )
    reg = brief["regimes"]
    assert set(reg.keys()) == {"trend_up", "range"}
    assert reg["trend_up"]["n_trades"] == 2
    assert reg["trend_up"]["total_pnl"] == 125.0

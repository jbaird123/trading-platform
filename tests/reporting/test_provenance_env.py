# Validates: [JSON-11.22], [JSON-11.23]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _make_trade(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_environment_and_provenance_defaults_present():
    trades = [
        _make_trade(datetime(2023, 1, 1, 0, 0), 10.0),
        _make_trade(datetime(2023, 1, 2, 0, 0), -5.0),
    ]

    brief = generate_brief(
        meta={"run_id": "r1", "strategy_name": "S"},
        params={},
        trades=trades,
        initial_cash=1000.0,
    )

    env = brief["environment"]
    prov = brief["provenance"]

    assert isinstance(env.get("python_version"), str)
    assert isinstance(env.get("platform"), str)
    assert "timezone" in env

    assert prov.get("run_id") == "r1"
    assert prov.get("strategy_name") == "S"
    assert isinstance(prov.get("symbols"), list)
    assert prov.get("data_start") is not None
    assert prov.get("data_end") is not None

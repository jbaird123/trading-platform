# Validates: [EL-8.5], [EL-8.7], [EL-8.8]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.execution import OandaStubAdapter
from trading_platform.execution.controller import run_live_controller
from trading_platform.portfolio.portfolio import PortfolioManager

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "EURUSD",
    "asset_class": "Forex",
    "point_value": 1.0,
    "tick_size": 0.00001,
    "pip_location": 0.0001,
}


def _df():
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    vals = [1.0, 2.0, 3.0, 2.0, 1.0]
    return pd.DataFrame(
        {
            "open": vals,
            "high": vals,
            "low": vals,
            "close": vals,
            "volume": [1] * 5,
        },
        index=idx,
    )


def _strat():
    return {
        "strategy_name": "LiveTest",
        "parameters": {},
        "long_entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"field": "close"},
                        "right": {"value": 1.5},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": {"field": "close"},
                        "right": {"value": 1.5},
                    }
                ]
            }
        ],
    }


def test_live_controller_happy_path_with_stub_adapter():
    df = _df()
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)
    res = run_live_controller(
        market_data=df, strategy_cfg=_strat(), adapter=adapter, pm=pm
    )
    # Should have placed at least one order and produced logs
    assert res.orders >= 1
    assert any(e.get("event") == "reconcile" for e in res.logs)
    # Ensure reconcile has a report with severity
    rec = [e for e in res.logs if e.get("event") == "reconcile"]
    assert rec and rec[0].get("report") and rec[0]["report"].get("severity")


def test_live_controller_dry_run_and_kill_switch():
    df = _df()
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)
    # Dry run emits logs and no orders
    res = run_live_controller(
        market_data=df, strategy_cfg=_strat(), adapter=adapter, pm=pm, dry_run=True
    )
    assert res.orders == 0
    assert any(e.get("event") == "dry_run" for e in res.logs)

    # Kill switch after a single order
    adapter2 = OandaStubAdapter(
        pm=PortfolioManager(
            base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
        )
    )
    res2 = run_live_controller(
        market_data=df,
        strategy_cfg=_strat(),
        adapter=adapter2,
        pm=adapter2.pm,  # type: ignore[arg-type]
        max_orders=1,
    )
    assert res2.orders == 1
    assert any(
        e.get("reason") == "kill_switch"
        for e in res2.logs
        if e.get("event") == "shutdown"
    )


def test_live_controller_reconciliation_detects_diff(monkeypatch):
    df = _df()
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)

    # Monkeypatch the adapter snapshot to force a mismatch
    def fake_snapshot():
        return {"open_side": "long", "size": 2.0}

    monkeypatch.setattr(adapter, "account_snapshot", fake_snapshot)
    res = run_live_controller(
        market_data=df, strategy_cfg=_strat(), adapter=adapter, pm=pm
    )
    # Look for reconcile event with report diffs/severity
    rec = [e for e in res.logs if e.get("event") == "reconcile"]
    assert rec and rec[0].get("report")
    assert rec[0]["report"].get("position_diffs")

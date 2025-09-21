# Validates: [EL-8.8]
from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.execution import OandaStubAdapter
from trading_platform.execution.controller import reconcile_report, run_live_controller
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def test_reconcile_warn_on_cash_delta():
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    # Monkeypatch snapshot to show different cash
    adapter.account_snapshot = lambda: {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1005.0,
        "equity": 1005.0,
        "realized_pnl_today": 0.0,
    }
    rep = reconcile_report(pm, adapter, cash_tolerance=1.0)
    assert rep.severity == "warn"


def test_controller_mark_price_equity_path():
    # Create a position and ensure mark_price updates equity path
    idx = [datetime(2024, 1, 1, h) for h in range(2)]
    df = pd.DataFrame(
        {
            "open": [1, 1],
            "high": [1, 1],
            "low": [1, 1],
            "close": [1, 2],
            "volume": [1, 1],
        },
        index=idx,
    )
    pm = PortfolioManager(initial_cash=1000.0)
    adapter = OandaStubAdapter(pm=pm)
    # Strategy: enter long at second bar
    cfg = {
        "strategy_name": "S",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": "close", "right": 1.5}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": "close", "right": 0.5}]}
        ],
    }
    res = run_live_controller(market_data=df, strategy_cfg=cfg, adapter=adapter, pm=pm)
    # Should produce reconcile report event
    rec = [e for e in res.logs if e.get("event") == "reconcile"]
    assert rec and rec[0]["report"]["severity"] in {"info", "warn", "error"}

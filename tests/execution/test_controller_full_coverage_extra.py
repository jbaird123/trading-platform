from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest
from trading_platform.execution import controller
from trading_platform.execution.controller import (
    ControllerResult,
    ReconcileReport,
    _realized_pnl_on,
)
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager


def _make_market(values: list[float]) -> pd.DataFrame:
    idx = [datetime(2024, 1, 1, h) for h in range(len(values))]
    return pd.DataFrame(
        {
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": [1] * len(values),
        },
        index=idx,
    )


def test_realized_pnl_on_filters_by_exit_date():
    day = datetime(2024, 2, 1).date()
    pm = PortfolioManager(initial_cash=0.0)
    pm.trades = cast(
        list[Any],
        [
            SimpleNamespace(pnl=5.0, exit_time=datetime(2024, 2, 1, 12)),
            SimpleNamespace(pnl=-2.0, exit_time=datetime(2024, 1, 31, 23)),
        ],
    )
    assert _realized_pnl_on(pm, day) == pytest.approx(5.0)


def test_reconcile_report_with_long_position_warns_on_cash_delta():
    pm = PortfolioManager(initial_cash=1_000.0)
    pm.create_new_position("EURUSD", "long", 1.10, 2.0, datetime(2024, 1, 1))
    mark = 1.20

    class StubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {
                "open_side": "long",
                "size": 2.0,
                "cash_balance": 990.0,
                "equity": 1010.0,
                "realized_pnl_today": 0.5,
            }

    rep = controller.reconcile_report(
        pm,
        cast(OandaStubAdapter, StubAdapter()),
        mark_price=mark,
        cash_tolerance=5.0,
        pnl_tolerance=0.2,
    )
    assert rep.severity == "warn"
    assert rep.position_diffs == []
    assert rep.deltas["equity"] > 0


def test_reconcile_report_with_short_position_info():
    pm = PortfolioManager(initial_cash=1_000.0)
    pm.create_new_position("EURUSD", "short", 1.10, 1.0, datetime(2024, 1, 1))

    class StubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {
                "open_side": "short",
                "size": 1.0,
                "cash_balance": 1_000.0,
                "equity": 1_000.0,
                "realized_pnl_today": 0.0,
            }

    rep = controller.reconcile_report(
        pm,
        cast(OandaStubAdapter, StubAdapter()),
        mark_price=1.05,
    )
    assert rep.severity == "info"
    assert rep.position_diffs == []


def test_reconcile_report_error_when_tolerances_exceeded():
    pm = PortfolioManager(initial_cash=500.0)
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class StubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {
                "open_side": "short",
                "size": 2.0,
                "cash_balance": 100.0,
                "equity": 100.0,
                "realized_pnl_today": 5.0,
            }

    rep = controller.reconcile_report(
        pm,
        cast(OandaStubAdapter, StubAdapter()),
        mark_price=1.10,
    )
    assert rep.severity == "error"
    assert set(rep.position_diffs) == {"side_mismatch", "size_mismatch"}


def test_reconcile_no_differences_returns_empty_list():
    pm = PortfolioManager(initial_cash=700.0)
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class StubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {"open_side": "long", "size": 1.0}

    assert (
        controller.reconcile(
            pm,
            cast(OandaStubAdapter, StubAdapter()),
        )
        == []
    )


def test_reconcile_report_with_size_tolerance():
    pm = PortfolioManager(initial_cash=800.0)
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class StubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {
                "open_side": "long",
                "size": 1.05,
                "cash_balance": 800.0,
                "equity": 800.0,
                "realized_pnl_today": 0.0,
            }

    rep = controller.reconcile_report(
        pm,
        cast(OandaStubAdapter, StubAdapter()),
        size_tolerance=0.1,
    )
    assert rep.severity == "info"
    assert rep.position_diffs == []


@dataclass
class StubOrder:
    status: str
    message: str = "ok"


class StubAdapter:
    def __init__(self, results: list[StubOrder], snapshot: dict[str, Any]) -> None:
        self._results = results
        self._snapshot = snapshot
        self.orders: list[dict[str, Any]] = []
        self.connected = False
        self.shutdowns: list[str] = []

    def connect(self) -> None:
        self.connected = True

    def shutdown(self) -> None:
        self.shutdowns.append("done")

    def place_order(self, **kwargs) -> StubOrder:
        self.orders.append(kwargs)
        if self._results:
            return self._results.pop(0)
        return StubOrder(status="accepted")

    def account_snapshot(self) -> dict[str, Any]:
        return self._snapshot


class StubStrategy:
    def __init__(self, signals: list[str]) -> None:
        self._signals = signals

    def generate_signals(self, market: pd.DataFrame) -> pd.Series:
        return pd.Series(self._signals, index=market.index)


def test_run_live_controller_dry_run(monkeypatch):
    adapter = StubAdapter([], {"open_side": None, "size": 0.0})
    pm = PortfolioManager(initial_cash=500.0)
    market = _make_market([1.0, 1.1])

    result = controller.run_live_controller(
        market_data=market,
        strategy_cfg={"strategy_name": "x"},
        adapter=cast(OandaStubAdapter, adapter),
        pm=pm,
        dry_run=True,
    )

    assert result == ControllerResult(orders=0, logs=result.logs)
    assert adapter.connected and adapter.shutdowns


def test_run_live_controller_with_orders_and_kill_switch(monkeypatch):
    signals = ["long", "flat", "long", "flat"]
    strategy = StubStrategy(signals)
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(initial_cash=1_000.0)
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    results = [StubOrder("accepted"), StubOrder("accepted"), StubOrder("accepted")]
    snapshot = {
        "open_side": "long",
        "size": 1.0,
        "cash_balance": 1_000.0,
        "equity": 1_000.0,
        "realized_pnl_today": 0.0,
    }
    adapter = StubAdapter(results, snapshot)

    monkeypatch.setattr(
        controller,
        "reconcile_report",
        lambda *a, **k: ReconcileReport("info", {}, []),
    )

    market = _make_market([1.0, 0.1, 1.2, 0.1])
    result = controller.run_live_controller(
        market_data=market,
        strategy_cfg={"strategy_name": "alt"},
        adapter=cast(OandaStubAdapter, adapter),
        pm=pm,
        max_orders=2,
    )

    assert result.orders == 2
    assert any(log.get("reason") == "kill_switch" for log in result.logs)


def test_run_live_controller_rejected_order_and_empty_prices(monkeypatch):
    signals = ["long", "short"]
    strategy = StubStrategy(signals)
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(initial_cash=1_000.0)

    results = [StubOrder("rejected", "no"), StubOrder("accepted")]
    snapshot = {"open_side": None, "size": 0.0, "cash_balance": 1_000.0}
    adapter = StubAdapter(results, snapshot)

    monkeypatch.setattr(
        controller,
        "reconcile_report",
        lambda *a, **k: ReconcileReport("info", {}, []),
    )

    market = _make_market([1.0, 1.1])
    result = controller.run_live_controller(
        market_data=market,
        strategy_cfg={"strategy_name": "rej"},
        adapter=cast(OandaStubAdapter, adapter),
        pm=pm,
    )

    statuses = [log.get("status") for log in result.logs if log.get("event") == "order"]
    assert statuses == ["rejected", "accepted"]


def test_run_live_controller_skips_flat_when_no_position(monkeypatch):
    signals = ["long", "flat"]
    strategy = StubStrategy(signals)
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(initial_cash=500.0)

    results = [StubOrder("accepted"), StubOrder("accepted")]
    snapshot = {"open_side": None, "size": 0.0, "cash_balance": 500.0}
    adapter = StubAdapter(results, snapshot)

    monkeypatch.setattr(
        controller,
        "reconcile_report",
        lambda *a, **k: ReconcileReport("info", {}, []),
    )

    market = _make_market([1.0, 0.9])
    result = controller.run_live_controller(
        market_data=market,
        strategy_cfg={"strategy_name": "flat"},
        adapter=cast(OandaStubAdapter, adapter),
        pm=pm,
    )

    orders = [log for log in result.logs if log.get("event") == "order"]
    assert len(orders) == 1


def test_run_live_controller_handles_empty_market(monkeypatch):
    strategy = StubStrategy([])
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(initial_cash=1_000.0)

    adapter = StubAdapter([], {"open_side": None, "size": 0.0})
    monkeypatch.setattr(
        controller,
        "reconcile_report",
        lambda *a, **k: ReconcileReport("info", {}, []),
    )

    market = pd.DataFrame()
    result = controller.run_live_controller(
        market_data=market,
        strategy_cfg={"strategy_name": "empty"},
        adapter=cast(OandaStubAdapter, adapter),
        pm=pm,
    )

    assert result.orders == 0
    assert any(log.get("event") == "reconcile" for log in result.logs)

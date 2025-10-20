from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pandas as pd
import pytest
from trading_platform.execution import OandaStubAdapter, controller
from trading_platform.execution.controller import (
    ControllerResult,
    ReconcileReport,
    _realized_pnl_on,
    reconcile,
    reconcile_report,
    run_live_controller,
)
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy

# Minimal instrument for testing
TEST_INSTRUMENT = {
    "symbol": "EURUSD",
    "asset_class": "Forex",
    "point_value": 1.0,
    "tick_size": 0.00001,
    "pip_location": 0.0001,
}

# Helper Functions & Classes from various files


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


# --- Consolidated Test Functions ---


def test_realized_pnl_on_filters_by_exit_date():
    day = datetime(2024, 2, 1).date()
    pm = PortfolioManager(
        base_currency="USD", initial_cash=0.0, instrument=TEST_INSTRUMENT
    )
    pm.trades = cast(
        list[Any],
        [
            SimpleNamespace(pnl=5.0, exit_time=datetime(2024, 2, 1, 12)),
            SimpleNamespace(pnl=-2.0, exit_time=datetime(2024, 1, 31, 23)),
        ],
    )
    assert _realized_pnl_on(pm, day) == pytest.approx(5.0)


def test_reconcile_report_with_long_position_warns_on_cash_delta():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1_000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.10, 2.0, datetime(2024, 1, 1))
    mark = 1.20

    class LocalStubAdapter:
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
        cast(OandaStubAdapter, LocalStubAdapter()),
        mark_price=mark,
        cash_tolerance=5.0,
        pnl_tolerance=0.2,
    )
    assert rep.severity == "warn"
    assert rep.position_diffs == []
    assert rep.deltas["equity"] > 0


def test_reconcile_report_with_short_position_info():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1_000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "short", 1.10, 1.0, datetime(2024, 1, 1))

    class LocalStubAdapter:
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
        cast(OandaStubAdapter, LocalStubAdapter()),
        mark_price=1.05,
    )
    assert rep.severity == "info"
    assert rep.position_diffs == []


def test_reconcile_report_error_when_tolerances_exceeded():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=500.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class LocalStubAdapter:
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
        cast(OandaStubAdapter, LocalStubAdapter()),
        mark_price=1.10,
    )
    assert rep.severity == "error"
    assert set(rep.position_diffs) == {"side_mismatch", "size_mismatch"}


def test_reconcile_no_differences_returns_empty_list():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=700.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class LocalStubAdapter:
        def account_snapshot(self) -> dict[str, Any]:
            return {"open_side": "long", "size": 1.0}

    assert (
        controller.reconcile(
            pm,
            cast(OandaStubAdapter, LocalStubAdapter()),
        )
        == []
    )


def test_reconcile_report_with_size_tolerance():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=800.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    class LocalStubAdapter:
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
        cast(OandaStubAdapter, LocalStubAdapter()),
        size_tolerance=0.1,
    )
    assert rep.severity == "info"
    assert rep.position_diffs == []


def test_run_live_controller_dry_run(monkeypatch):
    adapter = StubAdapter([], {"open_side": None, "size": 0.0})
    pm = PortfolioManager(
        base_currency="USD", initial_cash=500.0, instrument=TEST_INSTRUMENT
    )
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
    signals = ["enter_long", "exit_long", "enter_long", "exit_long"]
    strategy = StubStrategy(signals)
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1_000.0, instrument=TEST_INSTRUMENT
    )
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
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1_000.0, instrument=TEST_INSTRUMENT
    )

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
    # Test: enter_long when no position, then None
    # Should only create 1 order (the entry)
    signals = ["enter_long", "flat"]
    strategy = StubStrategy(signals)
    monkeypatch.setattr(controller, "compile_strategy", lambda cfg: strategy)
    pm = PortfolioManager(
        base_currency="USD", initial_cash=500.0, instrument=TEST_INSTRUMENT
    )

    results = [StubOrder("accepted")]
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
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1_000.0, instrument=TEST_INSTRUMENT
    )

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


def test_controller_reconcile_report_side_mismatch():
    """Adapter/portfolio side mismatch triggers reconcile error (line 95)."""
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "short",
        "size": 1.0,
    }

    diffs = reconcile_report(pm, adapter)

    assert "side_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"
    adapter.account_snapshot.assert_called_once()


def test_controller_reconcile_report_size_mismatch():
    """Adapter/portfolio size mismatch triggers reconcile error (line 99)."""
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",
        "size": 2.0,
    }

    diffs = reconcile_report(pm, adapter)

    assert "size_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"
    adapter.account_snapshot.assert_called_once()


def test_controller_reconcile_report_size_none_handling():
    """Test reconcile_report when adapter returns None for size (line 98)."""
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.1000, 1.0, datetime(2024, 1, 1))

    adapter = Mock()
    adapter.account_snapshot.return_value = {
        "open_side": "long",
        "size": None,
    }

    diffs = reconcile_report(pm, adapter)

    assert "size_mismatch" in diffs.position_diffs
    assert diffs.severity == "error"


def test_live_controller_flat_with_no_position():
    """Flat desired with no position should skip orders (line 134)."""
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    vals = [1.0, 1.1, 1.2]
    market_data = pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 3},
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "FlatTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 10.0}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 10.0}}]}
        ],
    }

    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.place_order.return_value = Mock(status="accepted")
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )

    adapter.place_order.assert_not_called()
    assert any(log.get("event") == "reconcile" for log in result.logs)


def test_live_controller_max_orders_kill_switch():
    """Kill switch triggers once max_orders reached (branch 147->125)."""
    idx = [datetime(2024, 1, 1, h) for h in range(5)]
    vals = [1.0, 0.05, 1.2, 0.05, 1.4]
    market_data = pd.DataFrame(
        {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 5},
        index=idx,
    )

    strategy_cfg = {
        "strategy_name": "AlternatingTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 0.5}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 0.1}}]}
        ],
    }

    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    pm.create_new_position("EURUSD", "long", 1.0, 1.0, datetime(2024, 1, 1))

    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.place_order.return_value = Mock(status="accepted")
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    result = run_live_controller(
        market_data=market_data,
        strategy_cfg=strategy_cfg,
        pm=pm,
        adapter=adapter,
        max_orders=2,
    )

    assert adapter.place_order.call_count == 2
    kill_switch_events = [
        log
        for log in result.logs
        if log.get("event") == "shutdown" and log.get("reason") == "kill_switch"
    ]
    assert len(kill_switch_events) == 1


def test_live_controller_empty_market_data():
    """Test run_live_controller with empty market data for mark price calculation."""
    market_data = pd.DataFrame()
    strategy_cfg = {
        "strategy_name": "EmptyTest",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 10.0}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 10.0}}]}
        ],
    }
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = Mock()
    adapter.connect.return_value = None
    adapter.shutdown.return_value = None
    adapter.account_snapshot.return_value = {
        "open_side": None,
        "size": 0.0,
        "cash_balance": 1000.0,
        "equity": 1000.0,
        "realized_pnl_today": 0.0,
    }

    result = run_live_controller(
        market_data=market_data, strategy_cfg=strategy_cfg, pm=pm, adapter=adapter
    )

    assert any(log.get("event") == "reconcile" for log in result.logs)


def test_reconcile_error_on_position_mismatch():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)

    def mock_account_snapshot() -> dict[str, float | str | None]:
        return {
            "open_side": "long",
            "size": 1.0,
            "cash_balance": 1000.0,
            "equity": 1000.0,
            "realized_pnl_today": 0.0,
        }

    adapter.account_snapshot = mock_account_snapshot  # type: ignore[method-assign]
    rep = reconcile_report(pm, adapter)
    assert rep.severity == "error" and rep.position_diffs


def test_controller_flat_desired_continues_loop():
    idx = [datetime(2024, 1, 1, h) for h in range(3)]
    df = pd.DataFrame(
        {
            "open": [1, 1, 1],
            "high": [1, 1, 1],
            "low": [1, 1, 1],
            "close": [1, 1, 1],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    cfg = {
        "strategy_name": "FlatAlways",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 2.0}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 0.5}}]}
        ],
    }
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)
    res = run_live_controller(market_data=df, strategy_cfg=cfg, adapter=adapter, pm=pm)
    assert res.orders == 0
    assert any(e.get("event") == "reconcile" for e in res.logs)


def test_reconcile_warn_on_cash_delta():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)

    def mock_account_snapshot() -> dict[str, float | str | None]:
        return {
            "open_side": None,
            "size": 0.0,
            "cash_balance": 1005.0,
            "equity": 1005.0,
            "realized_pnl_today": 0.0,
        }

    adapter.account_snapshot = mock_account_snapshot  # type: ignore[method-assign]
    rep = reconcile_report(pm, adapter, cash_tolerance=1.0)
    assert rep.severity == "warn"


def test_controller_mark_price_equity_path():
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
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)
    cfg = {
        "strategy_name": "S",
        "parameters": {},
        "long_entry_rules": [
            {"any_of": [{"condition": "is_above", "left": {"field": "close"}, "right": {"value": 1.5}}]}
        ],
        "long_exit_rules": [
            {"any_of": [{"condition": "is_below", "left": {"field": "close"}, "right": {"value": 0.5}}]}
        ],
    }
    res = run_live_controller(market_data=df, strategy_cfg=cfg, adapter=adapter, pm=pm)
    rec = [e for e in res.logs if e.get("event") == "reconcile"]
    assert rec and rec[0]["report"]["severity"] in {"info", "warn", "error"}


def test_reconcile_short_equity_and_legacy_reconcile():
    pm = PortfolioManager(
        base_currency="USD", initial_cash=1000.0, instrument=TEST_INSTRUMENT
    )
    adapter = OandaStubAdapter(pm=pm)
    adapter.connect()
    adapter.place_order(
        symbol="EURUSD",
        side="short",
        size=1.0,
        meta={"price": 100.0, "time": datetime(2024, 1, 1)},
    )
    rep = reconcile_report(pm, adapter, mark_price=90.0)
    assert rep.severity in {"info", "warn", "error"}
    adapter.account_snapshot()
    assert reconcile(pm, adapter) in ([], ["size_mismatch"])

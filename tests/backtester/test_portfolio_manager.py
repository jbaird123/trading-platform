from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pytest
from trading_platform.backtester.clock import ClockFrame
from trading_platform.backtester.models import ExecutionIntent
from trading_platform.backtester.portfolio_manager import (
    PortfolioManager,
    PortfolioStateError,
)
from trading_platform.portfolio.trade import Trade

from tests.backtester.factories import fill_factory, intent_factory


def _make_frame(minute: int) -> ClockFrame:
    open_time = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute)
    close_time = open_time + timedelta(minutes=1)
    series = pd.Series({"open": 1.0, "close": 1.0}, name=open_time)
    bar: dict[str, Any] = {"series": series}
    return ClockFrame(
        bar=bar,
        open_time=open_time,
        close_time=close_time,
        entry_open_time=open_time,
        decision_time=close_time,
    )


def _build_portfolio(**overrides: Any) -> PortfolioManager:
    params: dict[str, Any] = {
        "instrument": {"symbol": "EURUSD", "lot_size": 100000},
        "cost_model": {"spread_per_unit": 0.0002},
        "default_position_size": 10000.0,
        "entry_window_bars": 2,
        "max_positions_per_side": 1,
    }
    params.update(overrides)
    return PortfolioManager(**params)


def test_authorize_intents_assigns_size_and_tracks_pending_entry() -> None:
    pm = _build_portfolio(default_position_size=20000.0)
    intent = intent_factory(bar_index=10)

    sized = pm.authorize_intents([intent])

    assert len(sized) == 1
    assert pytest.approx(sized[0].decision.size) == 20000.0
    assert pm.pending_entry_count == 1


def test_authorize_intents_require_bar_index() -> None:
    pm = _build_portfolio()
    intent = intent_factory()
    object.__setattr__(intent.decision, "bar_index", None)

    with pytest.raises(PortfolioStateError):
        pm.authorize_intents([intent])


def test_apply_fill_opens_position_and_applies_costs() -> None:
    pm = _build_portfolio()
    sized_intent = pm.authorize_intents([intent_factory(bar_index=5)])[0]

    pm.apply_fill(fill_factory(intent=sized_intent, price=1.1000))

    active = pm.active_positions
    assert len(active) == 1
    position_view = active[0]
    # Entry price should reflect spread application (worse than mid).
    assert position_view.position.entry_price != pytest.approx(1.1000)
    assert position_view.position.context_at_entry == sized_intent.decision.context


def test_exit_fill_records_trade_and_clears_position() -> None:
    pm = _build_portfolio()
    sized_intent = pm.authorize_intents([intent_factory(bar_index=2)])[0]
    pm.apply_fill(fill_factory(intent=sized_intent, price=1.0000))

    exit_intent = ExecutionIntent(
        decision=sized_intent.decision,
        intent_type="exit",
        execution_model="next_bar_open",
    )
    sized_exit = pm.authorize_intents([exit_intent])[0]
    trade = pm.apply_fill(
        fill_factory(intent=sized_exit, price=1.0100, reason="strategy_exit")
    )

    assert isinstance(trade, Trade)
    assert trade.exit_reason == "strategy_exit"
    assert not pm.active_positions


def test_risk_fill_without_intent_closes_position() -> None:
    pm = _build_portfolio()
    sized_intent = pm.authorize_intents([intent_factory(bar_index=1)])[0]
    pm.apply_fill(fill_factory(intent=sized_intent, price=1.0050))

    trade = pm.apply_fill(
        fill_factory(
            intent=None,
            decision=sized_intent.decision,
            price=0.9950,
            reason="stop_loss",
        )
    )

    assert isinstance(trade, Trade)
    assert trade.exit_reason == "stop_loss"
    assert not pm.active_positions


def test_serialize_and_restore_entry_window_state() -> None:
    pm = _build_portfolio(entry_window_bars=3)
    pm.authorize_intents([intent_factory(bar_index=7)])
    state = pm.serialize_state()

    restored = _build_portfolio(entry_window_bars=3)
    restored.restore_state(state)

    assert restored.pending_entry_count == 1


def test_entry_window_expiration_removes_pending_entry() -> None:
    pm = _build_portfolio(entry_window_bars=1)
    pm.authorize_intents([intent_factory(bar_index=4)])
    pm.on_clock_tick(_make_frame(4))
    pm.on_clock_tick(_make_frame(5))

    assert pm.pending_entry_count == 0


def test_apply_fill_requires_known_intent() -> None:
    pm = _build_portfolio()
    orphan_intent = intent_factory(bar_index=3)

    with pytest.raises(PortfolioStateError):
        pm.apply_fill(fill_factory(intent=orphan_intent, price=1.0))

# Validates: [JSON-11.18]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.data.instrument import InstrumentDefinition
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _t(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="EURUSD",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.001,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_brief_includes_instrument_snapshot_when_provided():
    instr = InstrumentDefinition(
        symbol="EURUSD",
        tick_size=0.0001,
        base_ccy="EUR",
        quote_ccy="USD",
        asset_class="Forex",
        point_value=1.0,
        commission_model={},
        sessions=[],
    )
    # Cast symbol to string to satisfy typing
    instruments = {str(instr.symbol): instr.to_dict()}

    brief = generate_brief(
        meta={"run_id": "rX", "strategy_name": "S"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 10.0)],
        initial_cash=1000.0,
        instrument_definitions=instruments,
        cost_model={"type": "none"},
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )

    assert brief["instrument_definitions"]["EURUSD"]["tick_size"] == 0.0001
    assert brief["cost_model"]["type"] == "none"
    assert brief["fill_policy"]["policy"] == "market"
    assert brief["tie_break_policy"]["rule"] == "stop_then_tp"

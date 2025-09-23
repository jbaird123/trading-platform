# Validates: [JSON-11.18], [JSON-11.19], [JSON-11.20]
from __future__ import annotations

import json
from datetime import datetime, timedelta

from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade
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
    )


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


def test_finalize_run_uses_config_snapshots(tmp_path):
    run_path = tmp_path / "user" / "run123"
    cfg = RunConfig(
        user_id="user",
        run_id="run123",
        runs_dir=tmp_path,
        instrument_definitions={
            "EURUSD": {"symbol": "EURUSD", "tick_size": 0.0001, "base_ccy": "EUR"}
        },
        cost_model={"type": "none"},
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )

    out_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "run123"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 10.0)],
        initial_cash=1000.0,
        config=cfg,
    )

    data = json.loads(out_path.read_text())
    assert data["instrument_definitions"]["EURUSD"]["tick_size"] == 0.0001
    assert data["cost_model"]["type"] == "none"
    assert data["fill_policy"]["policy"] == "market"
    assert data["tie_break_policy"]["rule"] == "stop_then_tp"

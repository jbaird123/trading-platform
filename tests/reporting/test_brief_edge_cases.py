# Validates: [RV-9.1], [JSON-11.18]
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import (
    _percentile,
    compute_streaks,
    generate_brief,
)


def test_generate_brief_with_no_trades_produces_zeroed_metrics():
    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r0"},
        params={},
        trades=[],
        initial_cash=1000.0,
    )
    op = brief["overall_performance"]
    assert op["n_trades"] == 0
    assert op["final_equity"] == 1000.0
    dist = brief["distribution"]
    assert dist == {
        "pnl_mean": 0.0,
        "pnl_median": 0.0,
        "pnl_std": 0.0,
        "p05": 0.0,
        "p95": 0.0,
    }


def test_regimes_mismatch_results_in_empty_regimes_section():
    # Mismatched lengths should produce an empty regimes dict
    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r1"},
        params={},
        trades=[],
        initial_cash=1000.0,
        regimes_at_entry=["trend_up"],
    )
    assert brief["regimes"] == {}


def test_jsonable_handles_dataclass_values_and_datetimes():
    @dataclass
    class Dummy:
        when: datetime
        value: int

    d = Dummy(when=datetime(2023, 1, 1, 0, 0), value=42)
    brief = generate_brief(
        meta={"strategy_name": "S", "run_id": "r2"},
        params={},
        trades=[],
        initial_cash=1000.0,
        instrument_definitions={"DUMMY": d},
    )
    dd = brief["instrument_definitions"]["DUMMY"]
    # Dataclass converted to dict and datetime to isoformat
    assert dd["value"] == 42
    assert isinstance(dd["when"], str) and dd["when"].startswith("2023-01-01T00:00:00")


def test_percentile_and_streaks_additional_branches():
    # _percentile on empty list hits the early return
    assert _percentile([], 0.5) == 0.0

    # Streaks: include zero-pnl, consecutive wins, and a loss
    base = datetime(2023, 1, 1)
    trades = [
        Trade(
            symbol="X",
            entry_time=base,
            exit_time=base + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.0,
            side="long",
            size=1.0,
            pnl=0.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="X",
            entry_time=base + timedelta(days=1),
            exit_time=base + timedelta(days=1, hours=1),
            entry_price=1.0,
            exit_price=1.1,
            side="long",
            size=1.0,
            pnl=10.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="X",
            entry_time=base + timedelta(days=2),
            exit_time=base + timedelta(days=2, hours=1),
            entry_price=1.0,
            exit_price=1.2,
            side="long",
            size=1.0,
            pnl=20.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="X",
            entry_time=base + timedelta(days=3),
            exit_time=base + timedelta(days=3, hours=1),
            entry_price=1.0,
            exit_price=0.9,
            side="short",
            size=1.0,
            pnl=-10.0,
            exit_reason="signal",
        ),
    ]
    st = compute_streaks(trades)
    assert st["longest_win_streak"] >= 2
    assert st["longest_loss_streak"] >= 1

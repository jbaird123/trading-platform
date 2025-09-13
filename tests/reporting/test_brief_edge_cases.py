from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trading_platform.reporting.brief import generate_brief


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

# Validates: [RV-9.6]
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def _leaf_paths(obj, prefix=""):
    paths = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "field_definitions":
                continue
            p = f"{prefix}.{k}" if prefix else k
            paths |= _leaf_paths(v, p)
    elif isinstance(obj, list):
        if prefix == "trades" and obj and isinstance(obj[0], dict):
            for k in obj[0].keys():
                paths.add(f"trades[].{k}")
        else:
            paths.add(prefix)
    else:
        paths.add(prefix)
    return paths


def test_field_definitions_cover_all_leaf_paths():
    @dataclass
    class Dummy:
        when: datetime
        value: int

    brief = generate_brief(
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[],
        initial_cash=1000.0,
        instrument_definitions={"D": Dummy(when=datetime(2023, 1, 1), value=1)},
        cost_model={"commission": {"type": "per_unit", "value": 0.0}},
    )
    fd = brief.get("field_definitions", {})
    leafs = _leaf_paths(brief)
    missing = [p for p in leafs if p not in fd]
    assert not missing, f"Missing definitions for: {missing}"

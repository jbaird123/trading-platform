from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting import brief


def test_schema_lookup_handles_additional_properties_and_defaults() -> None:
    node = brief._schema_node_type({"type": ["string", "null"]})
    assert node == "null/string"
    assert brief._schema_node_type({}) == "object"

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "name"},
            "raw": "literal",
        },
        "description": "root",
    }
    properties = cast(dict[str, Any], schema["properties"])
    assert brief._lookup_schema(schema, ["name"]) == properties["name"]
    assert brief._lookup_schema(schema, ["raw", "child"]) is None
    assert brief._lookup_schema(schema, ["missing"]) == schema

    ap_schema = {
        "type": "object",
        "additionalProperties": {
            "type": "number",
            "description": "dynamic",
        },
    }
    expected = ap_schema["additionalProperties"]
    assert brief._lookup_schema(ap_schema, ["field"]) == expected

    ap_invalid = {"type": "object", "additionalProperties": True}
    assert brief._lookup_schema(ap_invalid, ["field"]) is None


def test_rounders_and_jsonable_cover_all_branches(tmp_path: Path) -> None:
    assert brief._round_percentage(None) == 0.0
    assert brief._round_price(None) is None

    @dataclass
    class Payload:
        value: int
        when: datetime
        path: Path

    payload = Payload(2, datetime(2024, 1, 1, 12, 0, 0), tmp_path / "f.txt")
    as_json = brief._to_jsonable(payload)
    assert as_json["when"].endswith("00:00")
    assert as_json["path"].endswith("f.txt")
    result = brief._to_jsonable({"items": [Path("a"), datetime(2024, 1, 1, 0, 0)]})
    assert result["items"][0] == "a"
    assert brief._percentile([], 0.5) == 0.0
    assert brief.compute_distribution([]) == brief.EMPTY_DISTRIBUTION


def _trade(pnl: float) -> Trade:
    entry = datetime(2024, 1, 1, 0, 0, 0)
    return Trade(
        symbol="EURUSD",
        entry_time=entry,
        exit_time=entry + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="test",
    )


def test_streaks_regimes_and_exposure_cover_branches() -> None:
    trades = [_trade(2.0), _trade(1.0), _trade(0.0), _trade(-1.0), _trade(-2.0)]
    streaks = brief.compute_streaks(trades)
    assert streaks["longest_win_streak"] == 2
    assert streaks["longest_loss_streak"] == 2
    assert streaks["current_streak"] == 2

    assert brief._median_holding_secs([]) == 0.0
    assert brief._median_holding_secs(trades) > 0

    regimes = brief._compute_regimes(trades, ["trend", "trend", "flat", "bear", "bear"])
    assert regimes["trend"]["n_trades"] == 2
    assert brief._compute_regimes(trades, None) == {}

    exposures = [
        (datetime(2024, 1, 1, 0, 0, 0), 0.0),
        (datetime(2024, 1, 1, 1, 0, 0), 2.5),
    ]
    metrics = brief._compute_exposure_metrics(exposures)
    assert metrics["peak_gross_exposure"] == brief._round_currency(2.5)
    assert brief._compute_exposure_metrics(None) == {}

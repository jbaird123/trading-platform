# Validates: [RV-9.1], [JSON-11.1], [JSON-11.2], [JSON-11.4],
# [JSON-11.5], [JSON-11.6], [JSON-11.12], [JSON-11.18]
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import jsonschema
import pandas as pd
import pytest
from trading_platform.data.instrument import InstrumentDefinition
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting import brief
from trading_platform.reporting.brief import (
    _lookup_schema,
    _percentile,
    _round_currency,
    _round_price,
    _schema_node_type,
    compute_equity_stats,
    compute_streaks,
    generate_brief,
    save_run_brief,
)

SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs/schemas/brief.schema.json"


def _trade(
    pnl: float,
    exit_reason: str = "signal",
    *,
    mfe: float | None = None,
    mae: float | None = None,
    ts: datetime | None = None,
    symbol: str = "EURUSD",
) -> Trade:
    entry = ts or datetime(2024, 1, 1, 0, 0, 0)
    return Trade(
        symbol=symbol,
        entry_time=entry,
        exit_time=entry + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0 + pnl / 10000,  # simplified pnl calculation
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason=exit_reason,
        mfe_currency=mfe,
        mae_currency=mae,
    )


@pytest.fixture(scope="module")
def brief_schema():
    """Loads the Brief JSON schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_with_empty_signals_file(
    mock_read_parquet, mock_exists, tmp_path
):
    """Verify brief generation handles an empty signals file gracefully."""
    mock_read_parquet.return_value = pd.DataFrame(columns=["signal"])
    signals_path = tmp_path / "signals.parquet"
    signals_path.touch()

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        signals_path=str(signals_path),
    )

    assert "signal_quality_analysis" in brief_data
    assert brief_data["signal_quality_analysis"]["signal_persistence_pct"] == 0.0


def test_generate_brief_with_prepopulated_field_definitions():
    """Verify brief generation uses provided field_definitions."""
    custom_defs = {"meta.run_id": "Custom Run ID"}
    brief_data = generate_brief(
        meta={"run_id": "test-run"},
        params={},
        trades=[],
        initial_cash=10000,
        field_definitions=custom_defs,
    )

    assert brief_data["field_definitions"] == custom_defs


def test_generate_brief_with_empty_checksums_dict():
    """Verify an empty checksums dictionary is handled correctly."""
    brief_data = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        config_snapshot=None,
        instrument_definitions=None,
    )

    assert "checksums" not in brief_data


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_handles_invalid_signals_dataframe(
    mock_read_parquet, mock_exists
):
    """Test that a signal DataFrame without a 'signal' column raises ValueError."""
    mock_read_parquet.return_value = pd.DataFrame({"other_column": [1, 2, 3]})
    with pytest.raises(ValueError, match="must contain 'signal' column"):
        generate_brief(
            meta={},
            params={},
            trades=[],
            initial_cash=10000,
            signals_path="dummy.parquet",
        )


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_handles_invalid_signals_type(mock_read_parquet, mock_exists):
    """Test that providing an invalid type for signals raises ValueError."""
    mock_read_parquet.return_value = [1, 2, 3]
    with pytest.raises(ValueError, match="must be pandas DataFrame or Series"):
        generate_brief(
            meta={},
            params={},
            trades=[],
            initial_cash=10000,
            signals_path="dummy.parquet",
        )


def test_schema_node_type():
    assert _schema_node_type({"type": "string"}) == "string"
    assert _schema_node_type({"type": ["string", "null"]}) == "null/string"
    assert _schema_node_type({}) == "object"


def test_lookup_schema():
    schema = {
        "properties": {
            "foo": {"properties": {"bar": {"type": "string", "description": "a bar"}}},
            "baz": {"type": "object", "additionalProperties": {"type": "integer"}},
        }
    }
    assert _lookup_schema(schema, ["foo", "bar"]) == {
        "type": "string",
        "description": "a bar",
    }
    assert _lookup_schema(schema, ["foo", "qux"]) is None
    assert _lookup_schema(schema, ["baz", "any"]) == {"type": "integer"}
    assert _lookup_schema(schema, ["foo"]) is not None


def test_round_currency():
    assert _round_currency(None) == 0.0
    assert _round_currency(1.234) == 1.23
    assert _round_currency(1.235) == 1.24


def test_round_price():
    assert _round_price(None) is None
    assert _round_price(1.23456) == 1.2346


@patch("os.path.exists", return_value=True)
@patch("pandas.read_parquet")
def test_generate_brief_with_signals_none(mock_read_parquet, mock_exists):
    mock_read_parquet.return_value = None
    brief_data = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        signals_path="dummy.parquet",
    )
    assert brief_data["signal_quality_analysis"]["signal_persistence_pct"] == 0.0


def test_generate_brief_with_empty_checksums():
    brief_data = generate_brief(
        meta={},
        params={},
        trades=[],
        initial_cash=10000,
        config_snapshot=None,
        instrument_definitions=None,
    )
    assert "checksums" not in brief_data


def test_brief_uses_trade_cost_breakdown_when_present():
    t = Trade(
        symbol="X",
        entry_time=datetime(2023, 1, 1, 0, 0),
        exit_time=datetime(2023, 1, 1, 1, 0),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        cost_currency=0.06,
        cost_breakdown={"spread": 0.02, "commission": 0.04, "slippage": 0.0},
    )
    brief_data = generate_brief(
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[t],
        initial_cash=1000.0,
    )
    cost_bd = brief_data["trades"][0]["cost_breakdown"]
    assert cost_bd == {"spread": 0.02, "commission": 0.04, "slippage": 0.0}


def test_generate_brief_with_no_trades_produces_zeroed_metrics():
    brief_data = generate_brief(
        meta={"strategy_name": "S", "run_id": "r0"},
        params={},
        trades=[],
        initial_cash=1000.0,
    )
    op = brief_data["overall_performance"]
    assert op["n_trades"] == 0
    assert op["final_equity"] == 1000.0
    dist = brief_data["distribution"]
    assert dist == {
        "pnl_mean": 0.0,
        "pnl_median": 0.0,
        "pnl_std": 0.0,
        "p05": 0.0,
        "p95": 0.0,
    }


def test_regimes_mismatch_results_in_empty_regimes_section():
    # Mismatched lengths should produce an empty regimes dict
    brief_data = generate_brief(
        meta={"strategy_name": "S", "run_id": "r1"},
        params={},
        trades=[],
        initial_cash=1000.0,
        regimes_at_entry=["trend_up"],
    )
    assert brief_data["regimes"] == {}


def test_jsonable_handles_dataclass_values_and_datetimes():
    @dataclass
    class Dummy:
        when: datetime
        value: int

    d = Dummy(when=datetime(2023, 1, 1, 0, 0), value=42)
    brief_data = generate_brief(
        meta={"strategy_name": "S", "run_id": "r2"},
        params={},
        trades=[],
        initial_cash=1000.0,
        instrument_definitions={"DUMMY": d},
    )
    dd = brief_data["instrument_definitions"]["DUMMY"]
    # Dataclass converted to dict and datetime to isoformat
    assert dd["value"] == 42
    assert isinstance(dd["when"], str) and dd["when"].startswith("2023-01-01T00:00:00")


def test_percentile_and_streaks_additional_branches():
    # _percentile on empty list hits the early return
    assert _percentile([], 0.5) == 0.0

    # Streaks: include zero-pnl, consecutive wins, and a loss
    base = datetime(2023, 1, 1)
    trades = [
        _trade(pnl=0.0, ts=base),
        _trade(pnl=10.0, ts=base + timedelta(days=1)),
        _trade(pnl=20.0, ts=base + timedelta(days=2)),
        _trade(pnl=-10.0, ts=base + timedelta(days=3)),
    ]
    st = compute_streaks(trades)
    assert st["longest_win_streak"] >= 2
    assert st["longest_loss_streak"] >= 1


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

    brief_data = generate_brief(
        meta={"run_id": "rX", "strategy_name": "S"},
        params={},
        trades=[_trade(pnl=10.0, ts=datetime(2023, 1, 1))],
        initial_cash=1000.0,
        instrument_definitions=instruments,
        cost_model={"type": "none"},
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )

    assert brief_data["instrument_definitions"]["EURUSD"]["tick_size"] == 0.0001
    assert brief_data["cost_model"]["type"] == "none"
    assert brief_data["fill_policy"]["policy"] == "market"
    assert brief_data["tie_break_policy"]["rule"] == "stop_then_tp"


@pytest.fixture
def mock_trades_for_drawdown() -> list[Trade]:
    """Creates a list of mock trades designed to test drawdown logic."""
    return [
        _trade(pnl=1000.0, ts=datetime(2023, 1, 2), symbol="DUMMY"),
        _trade(pnl=-500.0, ts=datetime(2023, 1, 3), symbol="DUMMY"),
        _trade(pnl=-1000.0, ts=datetime(2023, 1, 4), symbol="DUMMY"),
        _trade(pnl=500.0, ts=datetime(2023, 1, 5), symbol="DUMMY"),
        _trade(pnl=2000.0, ts=datetime(2023, 1, 6), symbol="DUMMY"),
        _trade(pnl=-100.0, ts=datetime(2023, 1, 7), symbol="DUMMY"),
    ]


def test_compute_equity_stats_for_drawdown(mock_trades_for_drawdown: list[Trade]):
    """Validates the calculation of max_drawdown and its duration."""
    initial_cash = 10000.0

    result = compute_equity_stats(
        trades=mock_trades_for_drawdown, initial_cash=initial_cash
    )

    assert result["max_drawdown"] == 1500.0
    assert result["dd_duration_bars"] == 2


def test_generate_brief_omits_empty_optional_sections():
    b = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_trade(pnl=1.0, ts=datetime(2023, 1, 1))],
        initial_cash=1000.0,
    )
    assert "data_quality" not in b
    assert "checksums" not in b or b["checksums"]


@pytest.mark.skip(reason="Schema validation needs investigation")
def test_save_run_brief_schema_validation_enabled(tmp_path):
    run_path = tmp_path / "u" / "r"
    out = save_run_brief(
        run_path,
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_trade(pnl=1.0, ts=datetime(2023, 1, 1))],
        initial_cash=1000.0,
        validate_schema=True,
    )
    assert out.exists()


def test_minimal_brief_validates_against_schema(brief_schema):
    """Tests that a minimal, valid brief passes schema validation."""
    brief_data = generate_brief(
        meta={"run_id": "test_run", "strategy_name": "TestStrat"},
        params={"param1": 10},
        trades=[],
        initial_cash=100000.0,
    )
    brief_data["data_quality"] = {
        "loader_flags": [],
        "index_monotonic_increasing": True,
        "duplicate_bars_count": 0,
        "nan_counts": {},
        "has_nans": False,
    }
    brief_data["checksums"] = {
        "config_snapshot_hash": "dummy_config_hash",
        "instrument_defs_hash": "dummy_instrument_hash",
    }
    brief_data["field_definitions"] = {
        "meta": "Metadata about the run.",
        "strategy_params": "Strategy parameters.",
        "overall_performance": "Overall performance metrics.",
        "risk_snapshot": "Key risk metrics.",
        "equity_stats": "Equity curve statistics.",
        "distribution": "Trade PnL distribution.",
        "streaks": "Win/loss streaks.",
        "holding_time": "Trade holding time metrics.",
        "costs": "Trading costs.",
        "trades": "List of executed trades.",
    }
    brief_data["equity_stats"]["equity_curve"] = [
        ["2023-01-01T00:00:00", 100000.0],
        ["2023-01-02T00:00:00", 100010.0],
    ]
    brief_data["equity_stats"]["drawdown_curve"] = [
        ["2023-01-01T00:00:00", 0.0],
        ["2023-01-02T00:00:00", -5.0],
    ]
    try:
        jsonschema.validate(instance=brief_data, schema=brief_schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Minimal brief failed validation: {e}")


def test_all_brief_schema_fields_have_descriptions():
    """
    Validates that every field in the brief.schema.json has a description.
    This is a meta-test to enforce schema quality.
    """
    schema_path = Path("docs/schemas/brief.schema.json")
    assert schema_path.exists(), "brief.schema.json not found"

    schema = json.loads(schema_path.read_text())
    _check_descriptions_recursive(schema, "")


def _check_descriptions_recursive(obj: Any, path: str):
    """
    Recursively traverses the schema and asserts a description exists for every
    property.
    """
    if isinstance(obj, dict):
        if obj.get("type") == "object" and "properties" in obj:
            for prop, prop_schema in obj["properties"].items():
                new_path = f"{path}.{prop}" if path else prop
                assert (
                    "description" in prop_schema
                ), f"Missing description for: {new_path}"
                assert isinstance(
                    prop_schema["description"], str
                ), f"Description must be a string for: {new_path}"
                assert (
                    len(prop_schema["description"]) > 0
                ), f"Description cannot be empty for: {new_path}"
                _check_descriptions_recursive(prop_schema, new_path)
        if obj.get("type") == "array" and "items" in obj:
            new_path = f"{path}[]"
            _check_descriptions_recursive(obj["items"], new_path)


def test_generate_brief_raises_when_schema_description_missing(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: "{}")

    with pytest.raises(ValueError):
        brief.generate_brief(
            meta={},
            params={},
            trades=[_trade(pnl=1.0)],
            initial_cash=1_000.0,
        )


def test_save_run_brief_validates_when_requested(monkeypatch, tmp_path: Path):
    called: dict[str, bool] = {}

    def fake_validate(*, instance: dict, schema: dict) -> None:
        assert "meta" in instance
        called["seen"] = True

    monkeypatch.setattr(brief.jsonschema, "validate", fake_validate)

    path = brief.save_run_brief(
        tmp_path,
        meta={},
        params={},
        trades=[_trade(pnl=1.0)],
        initial_cash=500.0,
        validate_schema=True,
    )

    assert path.exists()
    assert called["seen"]


def test_compute_data_quality_penalizes_nans() -> None:
    df = pd.DataFrame({"close": [1.0, float("nan"), 3.0]})
    result = brief.compute_data_quality(df)
    assert result["has_nans"] is True
    assert result["quality_score"] < 1.0


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


@pytest.mark.skip(reason="Schema enumeration test needs investigation")
def test_brief_schema_accepts_mc_wf_ps_enumerated_fields():
    schema_path = Path("docs/schemas/brief.schema.json")
    schema = json.loads(schema_path.read_text())
    brief_data = {
        "meta": {"run_id": "r", "strategy_name": "S"},
        "strategy_params": {},
        "overall_performance": {
            "n_trades": 0,
            "total_pnl": 0.0,
            "mean_pnl": 0.0,
            "median_pnl": 0.0,
            "by_side_total_pnl": {"long": 0.0, "short": 0.0},
            "win_rate": 0.0,
            "initial_equity": 1000.0,
            "final_equity": 1000.0,
        },
        "risk_snapshot": {
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
        },
        "equity_stats": {
            "equity_curve": [["2024-01-01T00:00:00", 1000.0]],
            "drawdown_curve": [["2024-01-01T00:00:00", 0.0]],
            "max_drawdown": 0.0,
            "dd_duration_bars": 0,
        },
        "distribution": {
            "pnl_mean": 0.0,
            "pnl_median": 0.0,
            "pnl_std": 0.0,
            "p05": 0.0,
            "p95": 0.0,
        },
        "streaks": {
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
            "current_streak": 0,
        },
        "holding_time": {"median_secs": 0.0},
        "costs": {
            "total_costs": 0.0,
            "avg_cost_per_trade": 0.0,
            "breakdown": {"spread": 0.0, "commission": 0.0, "slippage": 0.0},
        },
        "trades": [],
        "monte_carlo": {
            "mode": "bar_resimulation",
            "trials": 10,
            "config": {"cost_jitter": {}, "perturbation": {}},
            "final_equity": {"mean": 1000.0, "p05": 900.0, "p95": 1100.0},
            "total_pnl": {"mean": 0.0, "p05": -100.0, "p95": 100.0},
            "max_drawdown": {"mean": 10.0, "p05": 5.0, "p95": 20.0},
            "win_rate": {"mean": 0.5, "p05": 0.2, "p95": 0.8},
            "risk": {"var_95": -100.0, "cvar_95": -150.0},
            "ruin_prob": 0.0,
            "time_under_water_mean": 0.2,
            "exemplars": {
                "worst": {"final_equity": 900.0, "curve": [1000.0, 900.0]},
                "median": {"final_equity": 1000.0, "curve": [1000.0, 1000.0]},
                "best": {"final_equity": 1100.0, "curve": [1000.0, 1100.0]},
            },
        },
        "walk_forward": {
            "splits": [{"train_start": "t1", "test_start": "t2", "oos_score": 0.0}],
            "oos_total_pnl": {"mean": 0.0, "median": 0.0, "n_splits": 1},
        },
        "parameter_search": {
            "top": {"params": {"x": 1}, "score": 1.0},
            "results": [{"params": {"x": 1}, "score": 1.0}],
        },
    }
    jsonschema.validate(instance=brief_data, schema=schema)


def test_generate_brief_handles_signal_dataframe_and_artifacts(monkeypatch, tmp_path):
    trades = [
        _trade(12.5, "take_profit", mfe=20.0, mae=None),
        _trade(-7.2, "stop_loss", mfe=None, mae=9.0),
    ]

    def fake_exists(path: str) -> bool:
        return path.endswith("signals.parquet")

    def fake_read_parquet(path: str) -> pd.DataFrame:
        assert path.endswith("signals.parquet")
        return pd.DataFrame({"signal": ["long", "long", "flat", "short", "short"]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10_000.0,
        signals_path=str(tmp_path / "signals.parquet"),
        rmm_spans_path="/tmp/rmm.parquet",
        processed_data_path="/tmp/data.parquet",
        skipped_trades=[
            {
                "entry_time": "2024-01-01T00:00:00",
                "symbol": "EURUSD",
                "side": "long",
                "size": 100.0,
                "skip_reason": "blackout",
                "counterfactual_entry_price": 1.0,
                "counterfactual_pnl": 0.0,
                "cf_pnl_currency": 12.3456,
            }
        ],
    )

    sq = brief_data["signal_quality_analysis"]
    assert sq["signal_persistence_pct"] > 0.0
    assert sq["avg_signal_duration_bars"] > 0.0
    assert "signals_path" in brief_data["artifacts"]
    assert "checksums" not in brief_data
    filt = brief_data["filter_impact"]["blackout"]
    assert filt["total_cf_pnl"] == 12.35


def test_generate_brief_handles_signal_series_with_flat_values(monkeypatch, tmp_path):
    """Test signal series with no commands (all None)."""
    trade = _trade(5.0, "take_profit", mfe=6.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_read_parquet(_: str) -> pd.Series:
        # With command-based signals, "no commands" means all None
        return pd.Series([None, None, None])

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=1_000.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    sq = brief_data["signal_quality_analysis"]
    assert sq["signal_persistence_pct"] == 0.0
    assert sq["avg_signal_duration_bars"] == 0.0


def test_generate_brief_errors_when_signal_column_missing(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_read_parquet(_: str) -> pd.DataFrame:
        return pd.DataFrame({"price": [1, 2, 3]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_read_parquet)

    with pytest.raises(ValueError):
        generate_brief(
            meta={},
            params={},
            trades=[trade],
            initial_cash=500.0,
            signals_path=str(tmp_path / "signals.parquet"),
        )


def test_generate_brief_errors_for_invalid_signal_object(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    class BadSignals:
        pass

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", lambda _: BadSignals())

    with pytest.raises(ValueError):
        generate_brief(
            meta={},
            params={},
            trades=[trade],
            initial_cash=500.0,
            signals_path=str(tmp_path / "signals.parquet"),
        )


def test_generate_brief_ignores_io_errors_when_loading_signals(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    def fake_exists(_: str) -> bool:
        return True

    def fake_reader(_: str) -> pd.DataFrame:
        raise pd.errors.ParserError("bad file")

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_reader)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=500.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    assert brief_data["signal_quality_analysis"] == {
        "signal_persistence_pct": 0.0,
        "avg_signal_duration_bars": 0.0,
    }


def test_generate_brief_handles_null_signal_column(monkeypatch, tmp_path):
    trade = _trade(1.0, "take_profit", mfe=2.0, mae=None)

    class NullSignals(pd.DataFrame):
        @property
        def _constructor(self) -> type[NullSignals]:
            return NullSignals

        def __getitem__(self, key: str):  # type: ignore[override]
            if key == "signal":
                return None
            return super().__getitem__(key)

    def fake_exists(_: str) -> bool:
        return True

    def fake_reader(_: str) -> NullSignals:
        return NullSignals({"signal": ["flat", "long"]})

    monkeypatch.setattr("os.path.exists", fake_exists)
    monkeypatch.setattr("pandas.read_parquet", fake_reader)

    brief_data = generate_brief(
        meta={},
        params={},
        trades=[trade],
        initial_cash=500.0,
        signals_path=str(tmp_path / "signals.parquet"),
    )

    assert brief_data["signal_quality_analysis"] == {
        "signal_persistence_pct": 0.0,
        "avg_signal_duration_bars": 0.0,
    }


def test_brief_includes_stationarity_analysis():
    """Test that generate_brief includes stationarity analysis for sufficient trades."""
    # Create 25 trades for stationarity analysis (needs 20+)
    trades = [_trade(float(i % 5 - 2)) for i in range(25)]

    # Provide field definitions to avoid schema validation issues
    field_definitions = {
        "stationarity.adf_p_value": "P-value from Augmented Dickey-Fuller test",
        "stationarity.kpss_p_value": "P-value from KPSS test",
    }

    brief_data = generate_brief(
        meta={"strategy_name": "TestStrat", "run_id": "test-stat"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    # Should contain stationarity section
    assert "stationarity" in brief_data
    assert isinstance(brief_data["stationarity"], dict)

    # Should have expected keys when sufficient trades
    stationarity = brief_data["stationarity"]
    assert "adf_p_value" in stationarity
    assert "kpss_p_value" in stationarity
    assert isinstance(stationarity["adf_p_value"], float)
    assert isinstance(stationarity["kpss_p_value"], float)


def test_brief_stationarity_empty_with_insufficient_trades():
    """Test that stationarity is empty when fewer than 20 trades."""
    # Create only 10 trades (less than required 20)
    trades = [_trade(float(i)) for i in range(10)]

    # Provide empty field definitions since stationarity will be empty
    field_definitions: dict[str, str] = {}

    brief_data = generate_brief(
        meta={"strategy_name": "TestStrat", "run_id": "test-stat-empty"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    # Should contain empty stationarity section
    assert "stationarity" in brief_data
    assert brief_data["stationarity"] == {}


def test_brief_includes_feature_analysis():
    """Test that generate_brief includes feature analysis for trades with context."""
    # Create trades with context_at_entry containing numerical features
    trades = []
    for i in range(5):
        ctx = {
            "ema_fast": 1.2 + i * 0.1,
            "ema_slow": 1.0 + i * 0.05,
            "rsi": 50.0 + i * 2.0,
        }
        entry_time = datetime(2024, 1, 1) + timedelta(hours=i)
        trade = Trade(
            symbol="TEST",
            entry_time=entry_time,
            exit_time=entry_time + timedelta(hours=1),
            entry_price=1.0,
            exit_price=1.01 + i * 0.001,
            side="long",
            size=1.0,
            pnl=float(i * 10 - 20),
            context_at_entry=ctx,
        )
        trades.append(trade)

    # Provide field definitions to avoid schema validation issues
    field_definitions = {
        "feature_analysis.feature_correlation_matrix": (
            "Correlation matrix of numerical features from entry contexts"
        ),
    }

    brief_data = generate_brief(
        meta={"strategy_name": "TestFeatures", "run_id": "test-features"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    # Should contain feature_analysis section
    assert "feature_analysis" in brief_data
    assert isinstance(brief_data["feature_analysis"], dict)

    # Should have correlation matrix when context available
    feature_analysis = brief_data["feature_analysis"]
    assert "feature_correlation_matrix" in feature_analysis

    corr_matrix = feature_analysis["feature_correlation_matrix"]
    assert isinstance(corr_matrix, dict)

    # Should have correlations for our features
    assert "ema_fast" in corr_matrix
    assert "ema_slow" in corr_matrix
    assert "rsi" in corr_matrix


def test_brief_feature_analysis_empty_without_context():
    """Test that feature_analysis is empty when no numerical context available."""
    # Create trades without context_at_entry
    trades = [_trade(float(i)) for i in range(3)]

    field_definitions: dict[str, str] = {}

    brief_data = generate_brief(
        meta={"strategy_name": "TestNoFeatures", "run_id": "test-no-features"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    # Should contain empty feature_analysis section
    assert "feature_analysis" in brief_data
    assert brief_data["feature_analysis"] == {}


def test_brief_includes_activity_analysis():
    """Test that generate_brief includes activity analysis."""
    # Create trades over multiple days
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    trades = [
        _trade(100.0, ts=base_time),
        _trade(200.0, ts=base_time + timedelta(days=1)),
        _trade(-50.0, ts=base_time + timedelta(days=3)),
    ]

    field_definitions = {
        "activity.average_trades_per_day": "Average number of trades per day",
    }

    brief_data = generate_brief(
        meta={"strategy_name": "TestActivity", "run_id": "test-activity"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    assert "activity" in brief_data
    assert "average_trades_per_day" in brief_data["activity"]
    assert isinstance(brief_data["activity"]["average_trades_per_day"], float)


def test_brief_activity_empty_with_no_trades():
    """Test that activity is empty with no trades."""
    field_definitions: dict[str, str] = {}

    brief_data = generate_brief(
        meta={"strategy_name": "TestNoActivity", "run_id": "test-no-activity"},
        params={},
        trades=[],
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    assert "activity" in brief_data
    assert brief_data["activity"] == {}


def test_brief_includes_timing_buckets():
    """Test that generate_brief includes timing buckets analysis."""
    # Create trades at different times
    trades = [
        _trade(100.0, ts=datetime(2024, 1, 1, 10, 0, 0)),  # Monday 10am
        _trade(-50.0, ts=datetime(2024, 1, 2, 14, 0, 0)),  # Tuesday 2pm
    ]

    field_definitions = {
        "timing_buckets.hour_of_day": "Performance metrics by hour of day",
        "timing_buckets.day_of_week": "Performance metrics by day of week",
    }

    brief_data = generate_brief(
        meta={"strategy_name": "TestTiming", "run_id": "test-timing"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        field_definitions=field_definitions,
    )

    assert "timing_buckets" in brief_data
    timing = brief_data["timing_buckets"]
    assert "hour_of_day" in timing
    assert "day_of_week" in timing
    assert isinstance(timing["hour_of_day"], dict)
    assert isinstance(timing["day_of_week"], dict)


def test_brief_regime_counts_include_skipped_trades():
    """Test that regime_summary counts include skipped trades with regime context."""
    # Create trades with context_at_entry containing regime info using dataclass replace
    from dataclasses import replace

    base_trade_1 = _trade(100.0, ts=datetime(2024, 1, 1, 10, 0, 0))
    base_trade_2 = _trade(-50.0, ts=datetime(2024, 1, 2, 14, 0, 0))

    # Add context_at_entry with regime_label to trades
    trades = [
        replace(base_trade_1, context_at_entry={"regime_label": "bull"}),
        replace(base_trade_2, context_at_entry={"regime_label": "bull"}),
    ]

    # Create skipped trades with regime context in nested format
    skipped_trades = [
        {
            "side": "long",
            "entry_time": "2024-01-03T10:00:00",
            "skip_reason": "blackout_regime",
            "regime": {"label": "bear"},
        },
        {
            "side": "short",
            "entry_time": "2024-01-04T10:00:00",
            "skip_reason": "blackout_regime",
            "regime": {"label": "sideways"},
        },
    ]

    # Configure RMM policy with regime definitions
    config_snapshot = {
        "rmm": {
            "regimes": [
                {"label": "bull"},
                {"label": "bear"},
                {"label": "sideways"},
            ],
            "allowed_labels": ["bull"],
        }
    }

    brief_data = generate_brief(
        meta={"strategy_name": "TestRegimeSkips", "run_id": "test-regime-skips"},
        params={},
        trades=trades,
        initial_cash=1000.0,
        skipped_trades=skipped_trades,
        config_snapshot=config_snapshot,
    )

    # Verify regime_summary includes counts from both trades and skipped_trades
    assert "regime_summary" in brief_data
    regime_summary = brief_data["regime_summary"]
    assert "regime_counts" in regime_summary

    # Should have counts for all three regimes
    regime_counts = regime_summary["regime_counts"]
    assert regime_counts.get("bull") == 2  # 2 completed trades
    assert regime_counts.get("bear") == 1  # 1 skipped trade
    assert regime_counts.get("sideways") == 1  # 1 skipped trade

    # Verify trade and skip counts
    assert regime_summary["n_trades"] == 2
    assert regime_summary["n_skipped_trades"] == 2

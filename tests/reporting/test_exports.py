# Validates: [RV-9.4]
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import save_brief
from trading_platform.reporting.chart_export import (
    _read_prices_csv,
    save_chart_from_brief,
    save_features_for_chart,
)
from trading_platform.reporting.csv_export import save_prices_csv, save_trades_csv


def _t(ts: datetime, pnl: float) -> Trade:
    return Trade(
        symbol="X",
        entry_time=ts,
        exit_time=ts + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.001,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
        exit_reason="signal",
    )


def test_csv_export_save_prices_csv(tmp_path: Path):
    """Test save_prices_csv function coverage (lines 71-77)."""
    df = pd.DataFrame(
        {
            "open": [1.1000, 1.1010, 1.1020],
            "high": [1.1015, 1.1025, 1.1030],
            "low": [1.0995, 1.1005, 1.1015],
            "close": [1.1010, 1.1020, 1.1025],
            "volume": [100, 200, 150],
        }
    )
    df.index = pd.date_range("2024-01-01", periods=3, freq="1h")
    output_path = tmp_path / "test_prices.csv"
    result_path = save_prices_csv(output_path, df)
    assert result_path == output_path
    assert output_path.exists()
    content = output_path.read_text()
    assert "time,open,high,low,close" in content
    assert "volume" not in content
    assert output_path.parent.exists()


def test_finalize_run_writes_lightweight_chart(tmp_path):
    run_path = tmp_path / "user" / "run-chart"
    finalize_run(
        run_path,
        meta={"strategy_name": "SMA", "run_id": "run-chart"},
        params={},
        trades=[_t(datetime(2023, 1, 1, 9), 10.0), _t(datetime(2023, 1, 2, 9), -5.0)],
        initial_cash=1000.0,
    )
    out = run_path / "chart.html"
    assert out.exists()
    html = out.read_text()
    assert "lightweight-charts" in html and "createChart" in html
    assert "equity" in html


def test_chart_uses_prices_and_trades(tmp_path):
    run_path = tmp_path / "user" / "run-candles"
    run_path.mkdir(parents=True, exist_ok=True)
    (run_path / "prices.csv").write_text(
        "time,open,high,low,close\n"
        "2023-01-01T09:00:00,1.0,1.01,0.99,1.005\n"
        "2023-01-02T09:00:00,1.005,1.02,0.98,1.01\n"
    )
    brief = {
        "equity_stats": {"equity_curve": [["2023-01-01T09:00:00", 1000.0]]},
        "trades": [
            {
                "symbol": "X",
                "side": "long",
                "size": 1.0,
                "entry_time": "2023-01-01T09:00:00",
                "exit_time": "2023-01-02T09:00:00",
                "entry_price": 1.0,
                "exit_price": 1.01,
                "pnl": 10.0,
                "exit_reason": "signal",
            }
        ],
    }
    save_brief(brief, run_path / "brief.json")
    out = save_chart_from_brief(run_path)
    html = out.read_text()
    assert "Candlestick" in html or "candlestick" in html.lower()
    assert "rebuildTradeLines" in html
    assert "entry_time" in html and "exit_time" in html


def test_chart_renders_feature_panels(tmp_path):
    run = tmp_path / "u" / "r2"
    run.mkdir(parents=True, exist_ok=True)
    (run / "brief.json").write_text(
        json.dumps({"equity_stats": {"equity_curve": []}, "trades": []})
    )
    feats = {
        "meta": [
            {"name": "ema_fast", "type": "EMA", "columns": ["ema_fast"]},
            {"name": "rsi", "type": "RSI", "columns": ["rsi"]},
        ],
        "series": {
            "ema_fast": [["2023-01-01T00:00:00", 1.0]],
            "rsi": [["2023-01-01T00:00:00", 50.0]],
        },
    }
    (run / "features.json").write_text(json.dumps(feats))
    out = save_chart_from_brief(run)
    h = out.read_text()
    assert "features" in h and "panels" in h


def test_read_prices_csv_malformed_data(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    csv_content = (
        "time,open,high,low,close\n"
        "2023-01-01T09:00:00,1.0,1.01,0.99,1.005\n"
        "incomplete_line,1.0,1.01,0.99\n"
        "2023-01-02T09:00:00,invalid,text,data,here\n"
        "2023-01-03T09:00:00,1.005,1.02,0.98,1.01\n"
        "short\n"
    )
    (run_path / "prices.csv").write_text(csv_content)
    result = _read_prices_csv(run_path)
    assert len(result) == 2
    assert result[0] == ["2023-01-01T09:00:00", 1.0, 1.01, 0.99, 1.005]
    assert result[1] == ["2023-01-03T09:00:00", 1.005, 1.02, 0.98, 1.01]


def test_read_prices_csv_missing_file(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    result = _read_prices_csv(run_path)
    assert result == []


def test_save_chart_title_generation_edge_cases(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    malformed_brief = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": "not_a_dict",
    }
    (run_path / "brief.json").write_text(json.dumps(malformed_brief))
    out = save_chart_from_brief(run_path)
    html = out.read_text()
    assert "Run Charts" in html
    brief_with_run_id = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": {"run_id": "test-run-123"},
    }
    (run_path / "brief.json").write_text(json.dumps(brief_with_run_id))
    out = save_chart_from_brief(run_path)
    html = out.read_text()
    assert "test-run-123" in html
    brief_with_strategy = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": {"strategy_name": "TestStrategy"},
    }
    (run_path / "brief.json").write_text(json.dumps(brief_with_strategy))
    out = save_chart_from_brief(run_path)
    html = out.read_text()
    assert "TestStrategy" in html


def test_save_features_for_chart(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "time": ["2023-01-01T09:00:00", "2023-01-01T09:01:00"],
            "ema_fast": [1.0005, 1.0010],
            "ema_slow": [1.0010, 1.0015],
            "rsi": [65.5, 70.0],
            "volume": [1000, 1100],
            "signal": [1, 0],
            "bb_upper": [1.002, 1.003],
            "bb_lower": [0.998, 0.999],
        }
    )
    feature_specs = [
        {"name": "ema_fast", "type": "EMA", "columns": ["ema_fast"]},
        {"name": "ema_slow", "type": "EMA", "columns": ["ema_slow"]},
        {"name": "rsi", "type": "RSI", "columns": ["rsi"]},
        {"name": "volume", "type": "VOLUME", "columns": ["volume"]},
        {"name": "signal", "type": "SIGNAL", "columns": ["signal"]},
        {"name": "bb", "type": "BB", "columns": ["bb_upper", "bb_lower"]},
    ]
    result_path = save_features_for_chart(run_path, df, feature_specs)
    features_file = run_path / "features.json"
    assert features_file.exists()
    assert result_path == features_file
    saved_features = json.loads(features_file.read_text())
    assert "meta" in saved_features
    assert "series" in saved_features
    assert len(saved_features["meta"]) == 6


def test_save_features_for_chart_empty_data(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    result_path = save_features_for_chart(run_path, None, [])
    features_file = run_path / "features.json"
    assert features_file.exists()
    assert result_path == features_file
    content = json.loads(features_file.read_text())
    assert content == {}
    features_file.unlink()
    empty_df = pd.DataFrame()
    result_path = save_features_for_chart(run_path, empty_df, [])
    assert features_file.exists()
    content = json.loads(features_file.read_text())
    assert content == {}
    features_file.unlink()
    result_path = save_features_for_chart(run_path, "not_a_dataframe", [])
    assert features_file.exists()
    content = json.loads(features_file.read_text())
    assert content == {}


def test_save_features_for_chart_various_types(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "time": ["2023-01-01T09:00:00", "2023-01-01T09:01:00"],
            "ema": [1.0005, 1.0010],
            "sma": [1.0007, 1.0012],
            "rsi": [65.5, 70.0],
            "stoch": [80.0, 75.0],
            "macd_line": [0.001, 0.002],
            "macd_signal": [0.0008, 0.0018],
            "macd_histogram": [0.0002, 0.0002],
            "bb_upper": [1.002, 1.003],
            "bb_middle": [1.001, 1.002],
            "bb_lower": [0.998, 0.999],
            "signal": [1, 0],
            "volume": [1000, 1100],
            "unknown_feature": [42.0, 43.0],
        }
    )
    feature_specs = [
        {"name": "ema", "type": "EMA", "columns": ["ema"]},
        {"name": "sma", "type": "SMA", "columns": ["sma"]},
        {"name": "rsi", "type": "RSI", "columns": ["rsi"]},
        {"name": "stoch", "type": "STOCH", "columns": ["stoch"]},
        {
            "name": "macd",
            "type": "MACD",
            "columns": ["macd_line", "macd_signal", "macd_histogram"],
        },
        {"name": "bb", "type": "BB", "columns": ["bb_upper", "bb_middle", "bb_lower"]},
        {"name": "signal", "type": "SIGNAL", "columns": ["signal"]},
        {"name": "volume", "type": "VOLUME", "columns": ["volume"]},
        {"name": "unknown", "type": "UNKNOWN", "columns": ["unknown_feature"]},
    ]
    save_features_for_chart(run_path, df, feature_specs)
    features_file = run_path / "features.json"
    assert features_file.exists()
    saved_features = json.loads(features_file.read_text())
    assert "meta" in saved_features
    assert "series" in saved_features
    assert len(saved_features["meta"]) >= 7
    for meta_item in saved_features["meta"]:
        for column in meta_item["columns"]:
            assert column in saved_features["series"]


def test_save_features_for_chart_additional_types(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "time": ["2023-01-01T09:00:00", "2023-01-01T09:01:00"],
            "kc_upper": [1.002, 1.003],
            "kc_lower": [0.998, 0.999],
            "kc_middle": [1.000, 1.001],
            "psar": [1.0005, 1.0010],
            "psar_up": [1.0005, None],
            "psar_down": [None, 1.0010],
            "dc_upper": [1.003, 1.004],
            "dc_lower": [0.997, 0.998],
            "invalid_col": ["text", "data"],
        }
    )
    feature_specs = [
        {"name": "kc", "type": "KC", "columns": ["kc_upper", "kc_lower", "kc_middle"]},
        {"name": "psar", "type": "PSAR", "columns": ["psar", "psar_up", "psar_down"]},
        {"name": "dc", "type": "DC", "columns": ["dc_upper", "dc_lower"]},
        {"name": "", "type": "EMA", "columns": ["invalid"]},
        {"name": "test", "type": "", "columns": ["invalid"]},
        {"name": "invalid_data", "type": "CUSTOM", "columns": ["invalid_col"]},
    ]
    save_features_for_chart(run_path, df, feature_specs)
    features_file = run_path / "features.json"
    assert features_file.exists()
    saved_features = json.loads(features_file.read_text())
    assert len(saved_features["meta"]) >= 3
    kc_meta = next((m for m in saved_features["meta"] if m["name"] == "kc"), None)
    assert kc_meta is not None
    assert kc_meta["type"] == "KC"
    psar_meta = next((m for m in saved_features["meta"] if m["name"] == "psar"), None)
    assert psar_meta is not None
    assert psar_meta["type"] == "PSAR"
    dc_meta = next((m for m in saved_features["meta"] if m["name"] == "dc"), None)
    assert dc_meta is not None
    assert dc_meta["type"] == "DC"


def test_save_features_for_chart_missing_columns(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    df = pd.DataFrame({"time": ["2023-01-01T09:00:00"], "existing_col": [1.0]})
    feature_specs = [
        {"name": "missing_feature", "type": "EMA", "columns": ["nonexistent_col"]},
        {
            "name": "partial_feature",
            "type": "BB",
            "columns": ["bb_upper", "bb_lower", "bb_middle"],
        },
        {"name": "existing_feature", "type": "SMA", "columns": ["existing_col"]},
    ]
    save_features_for_chart(run_path, df, feature_specs)
    features_file = run_path / "features.json"
    assert features_file.exists()
    saved_features = json.loads(features_file.read_text())
    assert len(saved_features["meta"]) <= 1


def test_save_features_for_chart_float_conversion_error(tmp_path):
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    timestamps = pd.date_range("2023-01-01 09:00:00", periods=3, freq="1min")
    df = pd.DataFrame(
        {
            "mixed_col": [1.5, "not_a_number", None],
            "text_col": ["hello", "world", "test"],
            "good_col": [1.0, 2.0, 3.0],
        },
        index=timestamps,
    )
    feature_specs = [
        {"name": "mixed_col", "type": "EMA", "columns": ["mixed_col"]},
        {"name": "text_col", "type": "SMA", "columns": ["text_col"]},
        {"name": "good_col", "type": "RSI", "columns": ["good_col"]},
    ]
    save_features_for_chart(run_path, df, feature_specs)
    features_file = run_path / "features.json"
    assert features_file.exists()
    saved_features = json.loads(features_file.read_text())
    assert len(saved_features["meta"]) == 3
    mixed_series = saved_features["series"]["mixed_col"]
    assert len(mixed_series) == 1
    assert mixed_series[0][1] == 1.5
    text_series = saved_features["series"]["text_col"]
    assert len(text_series) == 0
    good_series = saved_features["series"]["good_col"]
    assert len(good_series) == 3


def test_save_trades_csv_writes_expected_columns(tmp_path: Path):
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
        r_multiple=1.0,
        mfe_currency=0.2,
        mae_currency=0.05,
        bars_held=3,
        cost_currency=0.01,
        cost_breakdown={"spread": 0.005, "commission": 0.003, "slippage": 0.002},
    )
    out = tmp_path / "runs" / "user" / "id" / "trades.csv"
    p = save_trades_csv(out, [t])
    assert p.exists()
    content = p.read_text()
    assert "symbol,side,size,entry_time,exit_time,entry_price,exit_price" in content
    assert (
        ",pnl,r_multiple,mfe_currency,mae_currency,bars_held,cost_currency,"
    ) in content
    assert ",spread,commission,slippage" in content

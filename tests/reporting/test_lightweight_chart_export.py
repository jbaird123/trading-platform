# Validates: [RV-9.4]
from __future__ import annotations

import json
from datetime import datetime, timedelta

from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.chart_export import save_chart_from_brief


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
    # The embedded equity array should have at least two points
    assert "equity" in html


def test_chart_uses_prices_and_trades(tmp_path):
    run_path = tmp_path / "user" / "run-candles"
    run_path.mkdir(parents=True, exist_ok=True)
    # Minimal prices.csv with two bars
    (run_path / "prices.csv").write_text(
        "time,open,high,low,close\n"
        "2023-01-01T09:00:00,1.0,1.01,0.99,1.005\n"
        "2023-01-02T09:00:00,1.005,1.02,0.98,1.01\n"
    )
    # Brief with trades
    from trading_platform.reporting.brief import save_brief

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
    # Ensure we embed trades JSON
    assert "entry_time" in html and "exit_time" in html


def test_chart_renders_feature_panels(tmp_path):
    run = tmp_path / "u" / "r2"
    run.mkdir(parents=True, exist_ok=True)
    # Minimal brief/equity to satisfy exporter
    (run / "brief.json").write_text(
        json.dumps({"equity_stats": {"equity_curve": []}, "trades": []})
    )
    # Provide features.json with one EMA overlay and one RSI panel
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
    """Test _read_prices_csv() with malformed CSV data - lines 411, 415-416."""
    from trading_platform.reporting.chart_export import _read_prices_csv

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create CSV with various malformed lines
    csv_content = """time,open,high,low,close
2023-01-01T09:00:00,1.0,1.01,0.99,1.005
incomplete_line,1.0,1.01,0.99
2023-01-02T09:00:00,invalid,text,data,here
2023-01-03T09:00:00,1.005,1.02,0.98,1.01
short
"""
    (run_path / "prices.csv").write_text(csv_content)

    result = _read_prices_csv(run_path)

    # Should only return the valid lines (first and fourth)
    assert len(result) == 2
    assert result[0] == ["2023-01-01T09:00:00", 1.0, 1.01, 0.99, 1.005]
    assert result[1] == ["2023-01-03T09:00:00", 1.005, 1.02, 0.98, 1.01]


def test_read_prices_csv_missing_file(tmp_path):
    """Test _read_prices_csv() with missing prices.csv file."""
    from trading_platform.reporting.chart_export import _read_prices_csv

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)
    # Don't create prices.csv file

    result = _read_prices_csv(run_path)

    # Should return empty list when file doesn't exist
    assert result == []


def test_save_chart_title_generation_edge_cases(tmp_path):
    """Test title generation edge cases - lines 439-440."""
    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Test case 1: malformed data that causes exception in title generation
    malformed_brief = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": "not_a_dict",  # This will cause isinstance check to fail
    }
    (run_path / "brief.json").write_text(json.dumps(malformed_brief))

    out = save_chart_from_brief(run_path)
    html = out.read_text()

    # Should fall back to default title "Run Charts" when exception occurs
    assert "Run Charts" in html

    # Test case 2: missing strategy_name but has run_id
    brief_with_run_id = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": {"run_id": "test-run-123"},
    }
    (run_path / "brief.json").write_text(json.dumps(brief_with_run_id))

    out = save_chart_from_brief(run_path)
    html = out.read_text()

    # Should use run_id as title when strategy_name is missing
    assert "test-run-123" in html

    # Test case 3: missing run_id but has strategy_name
    brief_with_strategy = {
        "equity_stats": {"equity_curve": []},
        "trades": [],
        "meta": {"strategy_name": "TestStrategy"},
    }
    (run_path / "brief.json").write_text(json.dumps(brief_with_strategy))

    out = save_chart_from_brief(run_path)
    html = out.read_text()

    # Should use strategy_name as title when run_id is missing
    assert "TestStrategy" in html


def test_save_features_for_chart(tmp_path):
    """Test save_features_for_chart function - lines 467-517."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create test dataframe with features
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

    # Create feature specs
    feature_specs = [
        {"name": "ema_fast", "type": "EMA", "columns": ["ema_fast"]},
        {"name": "ema_slow", "type": "EMA", "columns": ["ema_slow"]},
        {"name": "rsi", "type": "RSI", "columns": ["rsi"]},
        {"name": "volume", "type": "VOLUME", "columns": ["volume"]},
        {"name": "signal", "type": "SIGNAL", "columns": ["signal"]},
        {"name": "bb", "type": "BB", "columns": ["bb_upper", "bb_lower"]},
    ]

    # Save the features
    result_path = save_features_for_chart(run_path, df, feature_specs)

    # Verify features.json was created
    features_file = run_path / "features.json"
    assert features_file.exists()
    assert result_path == features_file

    # Verify content structure
    saved_features = json.loads(features_file.read_text())
    assert "meta" in saved_features
    assert "series" in saved_features
    assert len(saved_features["meta"]) == 6  # All feature specs should be included


def test_save_features_for_chart_empty_data(tmp_path):
    """Test save_features_for_chart with empty/None data."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Test with None dataframe
    result_path = save_features_for_chart(run_path, None, [])
    features_file = run_path / "features.json"
    assert features_file.exists()
    assert result_path == features_file
    # Should write empty JSON object
    content = json.loads(features_file.read_text())
    assert content == {}

    # Clean up for next test
    features_file.unlink()

    # Test with empty dataframe
    empty_df = pd.DataFrame()
    result_path = save_features_for_chart(run_path, empty_df, [])
    assert features_file.exists()
    content = json.loads(features_file.read_text())
    assert content == {}

    # Clean up for next test
    features_file.unlink()

    # Test with non-DataFrame object
    result_path = save_features_for_chart(run_path, "not_a_dataframe", [])
    assert features_file.exists()
    content = json.loads(features_file.read_text())
    assert content == {}


def test_save_features_for_chart_various_types(tmp_path):
    """Test save_features_for_chart with various types - covers _cols() branches."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create dataframe with features for different types
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

    # Test different feature types to cover all _cols() branches
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
        {
            "name": "unknown",
            "type": "UNKNOWN",
            "columns": ["unknown_feature"],
        },  # Default case
    ]

    save_features_for_chart(run_path, df, feature_specs)

    # Verify features.json was created and has expected structure
    features_file = run_path / "features.json"
    assert features_file.exists()

    saved_features = json.loads(features_file.read_text())
    assert "meta" in saved_features
    assert "series" in saved_features

    # Verify feature types processed (some filtered if columns missing from df)
    assert (
        len(saved_features["meta"]) >= 7
    )  # At least most features should be processed

    # Check that series data exists for features that were included
    [item["name"] for item in saved_features["meta"]]
    for meta_item in saved_features["meta"]:
        for column in meta_item["columns"]:
            assert column in saved_features["series"]


def test_save_features_for_chart_additional_types(tmp_path):
    """Test save_features_for_chart with KC, PSAR, DC types - covers missing lines."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create dataframe with features for the remaining uncovered types
    df = pd.DataFrame(
        {
            "time": ["2023-01-01T09:00:00", "2023-01-01T09:01:00"],
            "kc_upper": [1.002, 1.003],
            "kc_lower": [0.998, 0.999],
            "kc_middle": [1.000, 1.001],
            "psar": [1.0005, 1.0010],
            "psar_up": [1.0005, None],  # Test None values for float conversion
            "psar_down": [None, 1.0010],
            "dc_upper": [1.003, 1.004],
            "dc_lower": [0.997, 0.998],
            "invalid_col": [
                "text",
                "data",
            ],  # Non-numeric data to test exception handling
        }
    )

    # Test the remaining feature types and edge cases
    feature_specs = [
        {
            "name": "kc",
            "type": "KC",
            "columns": ["kc_upper", "kc_lower", "kc_middle"],
        },  # Line 480
        {
            "name": "psar",
            "type": "PSAR",
            "columns": ["psar", "psar_up", "psar_down"],
        },  # Line 486
        {"name": "dc", "type": "DC", "columns": ["dc_upper", "dc_lower"]},  # Line 488
        {"name": "", "type": "EMA", "columns": ["invalid"]},  # Empty name - line 499
        {"name": "test", "type": "", "columns": ["invalid"]},  # Empty type - line 499
        {
            "name": "invalid_data",
            "type": "CUSTOM",
            "columns": ["invalid_col"],
        },  # Lines 510-511 float conversion
    ]

    save_features_for_chart(run_path, df, feature_specs)

    # Verify features.json was created
    features_file = run_path / "features.json"
    assert features_file.exists()

    saved_features = json.loads(features_file.read_text())

    # Should have KC, PSAR, and DC features (empty name/type should be skipped)
    # invalid_data with text still has meta but empty series due to conversion failures
    assert len(saved_features["meta"]) >= 3  # At least kc, psar, dc

    # Verify KC type was processed
    kc_meta = next((m for m in saved_features["meta"] if m["name"] == "kc"), None)
    assert kc_meta is not None
    assert kc_meta["type"] == "KC"

    # Verify PSAR type was processed
    psar_meta = next((m for m in saved_features["meta"] if m["name"] == "psar"), None)
    assert psar_meta is not None
    assert psar_meta["type"] == "PSAR"

    # Verify DC type was processed
    dc_meta = next((m for m in saved_features["meta"] if m["name"] == "dc"), None)
    assert dc_meta is not None
    assert dc_meta["type"] == "DC"


def test_save_features_for_chart_missing_columns(tmp_path):
    """Test save_features_for_chart when expected columns are missing from dataframe."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create dataframe missing most expected columns
    df = pd.DataFrame(
        {
            "time": ["2023-01-01T09:00:00"],
            "existing_col": [1.0],
        }
    )

    # Feature specs expecting columns that don't exist
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

    # Features with no matching columns should be excluded
    # The existing_col should be included if it exists in the dataframe
    assert len(saved_features["meta"]) <= 1


def test_save_features_for_chart_float_conversion_error(tmp_path):
    """Test save_features_for_chart with unconvertible float values - lines 510-511."""
    import json

    import pandas as pd
    from trading_platform.reporting.chart_export import save_features_for_chart

    run_path = tmp_path / "test_run"
    run_path.mkdir(parents=True)

    # Create dataframe with mixed data types causing float conversion errors
    timestamps = pd.date_range("2023-01-01 09:00:00", periods=3, freq="1min")
    df = pd.DataFrame(
        {
            "mixed_col": [
                1.5,
                "not_a_number",
                None,
            ],  # Will trigger exception on line 510-511
            "text_col": ["hello", "world", "test"],  # All non-numeric
            "good_col": [1.0, 2.0, 3.0],  # All numeric, should work
        },
        index=timestamps,
    )

    # Function uses _cols() to determine expected column names, not provided columns
    # For EMA type, _cols("mixed", "EMA") returns ["mixed"], not ["mixed_col"]
    feature_specs = [
        {
            "name": "mixed_col",
            "type": "EMA",
            "columns": ["mixed_col"],
        },  # Name matches column
        {"name": "text_col", "type": "SMA", "columns": ["text_col"]},
        {"name": "good_col", "type": "RSI", "columns": ["good_col"]},
    ]

    save_features_for_chart(run_path, df, feature_specs)

    features_file = run_path / "features.json"
    assert features_file.exists()

    saved_features = json.loads(features_file.read_text())

    # All features should have meta entries (columns exist in df)
    assert len(saved_features["meta"]) == 3

    # Check the mixed_col series - should only have the valid float value
    mixed_series = saved_features["series"]["mixed_col"]
    assert len(mixed_series) == 1  # Only first value (1.5) should be included
    assert mixed_series[0][1] == 1.5

    # Check text_col series - should be empty due to no valid floats
    text_series = saved_features["series"]["text_col"]
    assert len(text_series) == 0

    # Check good_col series - should have all values
    good_series = saved_features["series"]["good_col"]
    assert len(good_series) == 3

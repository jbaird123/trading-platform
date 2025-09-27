# Validates: [RV-9.4]
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.html_export import (
    _spark_svg,
    _to_ts,
    generate_html_report,
)


def test_generate_html_report_spark_svg_returns_empty_string():
    """
    Test to hit the missing branch 140->148 by mocking _spark_svg to return empty.
    """
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    with patch("trading_platform.reporting.html_export._spark_svg", return_value=""):
        html = generate_html_report(
            meta={"strategy_name": "TestStrategy", "run_id": "test-123"},
            trades=[trade],
            price_series=[(datetime(2024, 1, 1, 10, 0), 1.1000)],
            overlays_data={"sma": [(datetime(2024, 1, 1), 1.1025)]},
        )

    assert "Trading Report - TestStrategy" in html
    assert "Run ID: test-123" in html
    assert "Trades: 1" in html
    assert "EURUSD" in html
    assert "<h2>Price</h2>" not in html
    assert "<div class='legend'><span>Price</span>" not in html


def test_generate_html_report_with_non_empty_price_series_for_comparison():
    """
    Test the opposite case where svg is not empty to ensure branch works correctly.
    """
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "TestStrategy"},
        trades=[trade],
        price_series=[
            (datetime(2024, 1, 1, 10, 0), 1.1000),
            (datetime(2024, 1, 1, 11, 0), 1.1050),
        ],
        overlays_data={"sma": [(datetime(2024, 1, 1, 10, 30), 1.1025)]},
    )

    assert "<h2>Price</h2>" in html
    assert "<div class='legend'>" in html
    assert "<svg" in html


def test_generate_html_report_dict_price_series_with_empty_sub_series():
    """
    Test dict price_series where individual series might be empty.
    """
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "MultiSymbol"},
        trades=[trade],
        price_series={
            "EURUSD": [],
            "GBPUSD": [(datetime(2024, 1, 1, 10, 0), 1.2500)],
        },
    )

    assert "<h2>Prices</h2>" in html
    assert "EURUSD" in html
    assert "GBPUSD" in html


def test_generate_html_report_no_overlays_in_meta():
    """Test when meta doesn't contain overlays key."""
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "TestStrategy"},
        trades=[trade],
    )

    assert "No overlays declared" in html
    assert "<h2>Overlays</h2>" in html


def test_generate_html_report_empty_overlays_list():
    """Test when meta contains empty overlays list."""
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": []},
        trades=[trade],
    )

    assert "No overlays declared" in html


def test_generate_html_report_non_list_overlays():
    """Test when meta contains overlays that isn't a list."""
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": "not-a-list"},
        trades=[trade],
    )

    assert "No overlays declared" in html


def test_generate_html_report_with_overlays_list_coverage_lines_118_121():
    """Test the overlays list generation to hit lines 118-121."""
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": ["SMA_20", "EMA_50", "RSI"]},
        trades=[trade],
    )

    assert "<ul>" in html
    assert "<li>SMA_20</li>" in html
    assert "<li>EMA_50</li>" in html
    assert "<li>RSI</li>" in html
    assert "</ul>" in html


def test_generate_html_report_dict_price_series_with_overlays_line_132():
    """Test dict price_series with overlays_data to hit line 132."""
    trade = Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=100000,
        pnl=500.0,
        exit_reason="signal",
    )

    html = generate_html_report(
        meta={"strategy_name": "MultiSymbol"},
        trades=[trade],
        price_series={
            "EURUSD": [(datetime(2024, 1, 1, 10, 0), 1.1000)],
            "GBPUSD": [(datetime(2024, 1, 1, 10, 0), 1.2500)],
        },
        overlays_data={
            "SMA_20": [(datetime(2024, 1, 1, 10, 0), 1.1025)],
            "EMA_50": [(datetime(2024, 1, 1, 10, 0), 1.1020)],
        },
    )

    assert "<div class='legend'><span>Price</span>" in html
    assert "<span>SMA_20</span>" in html
    assert "<span>EMA_50</span>" in html
    assert "</div>" in html


def test_spark_svg_no_overlays():
    """Test _spark_svg with no overlays (branch 55->63)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    entry_exit_ts = [(dates[0].to_pydatetime(), dates[2].to_pydatetime())]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result
    assert "class='ov'" not in result


def test_spark_svg_missing_entry_timestamp():
    """Test _spark_svg when entry timestamp not found in xs_map (branch 69->73)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    missing_entry_date = datetime(2023, 12, 31)
    entry_exit_ts = [(missing_entry_date, dates[1].to_pydatetime())]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result


def test_spark_svg_missing_exit_timestamp():
    """Test _spark_svg when exit timestamp not found in xs_map (branch 73->66)."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    missing_exit_date = datetime(2023, 12, 31)
    entry_exit_ts = [(dates[0].to_pydatetime(), missing_exit_date)]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result


def test_spark_svg_both_timestamps_missing():
    """Test _spark_svg when both entry and exit timestamps are missing."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    missing_entry = datetime(2023, 12, 30)
    missing_exit = datetime(2023, 12, 31)
    entry_exit_ts = [(missing_entry, missing_exit)]

    result = _spark_svg(prices, {}, entry_exit_ts)
    assert "<svg" in result


def test_spark_svg_empty_entry_exit_list():
    """Test _spark_svg with empty entry_exit_ts list."""
    dates = pd.date_range("2024-01-01", periods=3, freq="1D")
    prices = [(dates[0], 1.1000), (dates[1], 1.1050), (dates[2], 1.1025)]

    result = _spark_svg(prices, {}, [])
    assert "<svg" in result
    assert "class='mk'" not in result
    assert "class='mk2'" not in result


def test__to_ts_invalid_string_returns_min():
    out = _to_ts("not-a-date")
    assert isinstance(out, datetime) and out == datetime.min


def test__spark_svg_empty_series_returns_empty():
    assert _spark_svg([], {}, []) == ""


def test_generate_html_report_without_run_id_omits_runid_line():
    html = generate_html_report(meta={"strategy_name": "X"}, trades=[])
    assert "Trading Report - X" in html
    assert "Run ID:" not in html

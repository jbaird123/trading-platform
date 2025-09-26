"""
Comprehensive test coverage for reporting/html_export.py to achieve 100% coverage.

This file targets the missing branch coverage identified in the coverage report.
"""

from datetime import datetime

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.html_export import generate_html_report


def test_generate_html_report_spark_svg_returns_empty_string():
    """
    Test to hit the missing branch 140->148 by mocking _spark_svg to return empty.

    This is the most direct way to test the specific branch where:
    - price_series is not a dict (else branch)
    - _spark_svg returns "" (if svg: evaluates to False)
    """
    from unittest.mock import patch

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

    # Mock _spark_svg to return empty string to trigger the missing branch
    with patch("trading_platform.reporting.html_export._spark_svg", return_value=""):
        html = generate_html_report(
            meta={"strategy_name": "TestStrategy", "run_id": "test-123"},
            trades=[trade],
            price_series=[(datetime(2024, 1, 1, 10, 0), 1.1000)],  # Non-dict, non-empty
            overlays_data={"sma": [(datetime(2024, 1, 1), 1.1025)]},
        )

    # Verify the basic structure
    assert "Trading Report - TestStrategy" in html
    assert "Run ID: test-123" in html
    assert "Trades: 1" in html
    assert "EURUSD" in html

    # The key test: Price section should NOT be added because svg was empty
    # This hits the missing branch 140->148 where 'if svg:' is False
    assert "<h2>Price</h2>" not in html
    # The legend section should also be skipped
    assert "<div class='legend'><span>Price</span>" not in html


def test_generate_html_report_with_non_empty_price_series_for_comparison():
    """
    Test the opposite case where svg is not empty to ensure branch works correctly.
    """
    # Create a simple trade
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

    # Test with non-empty price_series
    html = generate_html_report(
        meta={"strategy_name": "TestStrategy"},
        trades=[trade],
        price_series=[
            (datetime(2024, 1, 1, 10, 0), 1.1000),
            (datetime(2024, 1, 1, 11, 0), 1.1050),
        ],
        overlays_data={"sma": [(datetime(2024, 1, 1, 10, 30), 1.1025)]},
    )

    # Verify the Price section IS added when svg is not empty
    assert "<h2>Price</h2>" in html
    assert "<div class='legend'>" in html
    assert "<svg" in html


def test_generate_html_report_dict_price_series_with_empty_sub_series():
    """
    Test dict price_series where individual series might be empty.
    This tests the dict branch but with empty sub-series.
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

    # Dict price_series with empty sub-series
    html = generate_html_report(
        meta={"strategy_name": "MultiSymbol"},
        trades=[trade],
        price_series={
            "EURUSD": [],  # Empty series
            "GBPUSD": [(datetime(2024, 1, 1, 10, 0), 1.2500)],  # Non-empty
        },
    )

    # Should have the Prices header (plural, for dict case)
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

    # Meta without overlays key
    html = generate_html_report(
        meta={"strategy_name": "TestStrategy"},  # No 'overlays' key
        trades=[trade],
    )

    # Should show "No overlays declared"
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

    # Meta with empty overlays list
    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": []},
        trades=[trade],
    )

    # Should show "No overlays declared"
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

    # Meta with overlays that's not a list
    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": "not-a-list"},
        trades=[trade],
    )

    # Should show "No overlays declared" since isinstance(m_over, list) is False
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

    # Meta with overlays list to hit the 'if overlays:' branch on lines 118-121
    html = generate_html_report(
        meta={"strategy_name": "TestStrategy", "overlays": ["SMA_20", "EMA_50", "RSI"]},
        trades=[trade],
    )

    # Should show the overlays list
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

    # Dict price_series with overlays_data to hit the loop on line 132
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

    # Should have the legend with overlay names (line 132 loop)
    assert "<div class='legend'><span>Price</span>" in html
    assert "<span>SMA_20</span>" in html
    assert "<span>EMA_50</span>" in html
    assert "</div>" in html

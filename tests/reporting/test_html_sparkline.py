# Validates: [RV-9.3]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.html_export import generate_html_report


def _series():
    base = datetime(2024, 1, 1, 0, 0)
    ts = [base + timedelta(minutes=10 * i) for i in range(6)]
    vals = [100.0, 101.0, 100.5, 102.0, 101.5, 103.0]
    return list(zip(ts, vals))


def _overlays():
    base = datetime(2024, 1, 1, 0, 0)
    ts = [base + timedelta(minutes=10 * i) for i in range(6)]
    ema = [100.0, 100.6, 100.7, 101.2, 101.3, 101.8]
    return {"ema": list(zip(ts, ema))}


def test_generate_html_report_includes_svg_sparkline_and_markers():
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1, 0, 10),
        exit_time=datetime(2024, 1, 1, 0, 50),
        entry_price=101.0,
        exit_price=101.5,
        side="long",
        size=1.0,
        pnl=0.5,
    )
    html = generate_html_report(
        {"strategy_name": "S", "run_id": "r", "overlays": ["ema"]},
        [t],
        price_series=_series(),
        overlays_data=_overlays(),
    )
    assert "<svg" in html and "polyline" in html
    assert "class='ov'" in html  # overlay line present
    assert "class='mk'" in html and "class='mk2'" in html  # entry/exit markers

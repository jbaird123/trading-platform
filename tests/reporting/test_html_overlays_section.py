from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.html_export import generate_html_report


def test_html_report_lists_overlays_when_present():
    meta = {"strategy_name": "S", "run_id": "r", "overlays": ["ema_fast", "ema_slow"]}
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.1,
        side="long",
        size=1.0,
        pnl=0.1,
    )
    html = generate_html_report(meta, [t])
    assert "<h2>Overlays</h2>" in html
    assert "ema_fast" in html and "ema_slow" in html
    assert "Entries/Exits" in html


def test_html_report_shows_no_overlays_message_when_absent():
    meta = {"strategy_name": "S", "run_id": "r"}
    html = generate_html_report(meta, [])
    assert "No overlays declared." in html

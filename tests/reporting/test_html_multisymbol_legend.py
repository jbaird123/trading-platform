from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.reporting.html_export import generate_html_report


def _series(sym: str):
    base = datetime(2024, 1, 1, 0, 0)
    ts = [base + timedelta(minutes=10 * i) for i in range(3)]
    vals = [1.0, 1.1, 1.2]
    return sym, list(zip(ts, vals))


def test_html_report_multisymbol_and_legend():
    s1 = _series("EURUSD")
    s2 = _series("USDJPY")
    price = {s1[0]: s1[1], s2[0]: s2[1]}
    meta = {"strategy_name": "S", "run_id": "r", "overlays": ["ema"]}
    html = generate_html_report(
        meta, [], price_series=price, overlays_data={"ema": s1[1]}
    )
    assert "Prices" in html and "EURUSD" in html and "USDJPY" in html
    assert "legend" in html and "ema" in html

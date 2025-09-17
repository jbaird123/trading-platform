# Validates: [RV-9.4]
from __future__ import annotations

from trading_platform.reporting.html_export import generate_html_report


def test_generate_html_report_without_run_id_omits_runid_line():
    html = generate_html_report(meta={"strategy_name": "X"}, trades=[])
    assert "Trading Report - X" in html
    assert "Run ID:" not in html

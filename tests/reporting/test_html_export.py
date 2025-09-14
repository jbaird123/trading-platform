from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.core.run import finalize_run
from trading_platform.portfolio.trade import Trade


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


def test_finalize_run_writes_html_report(tmp_path):
    run_path = tmp_path / "user" / "run-html"
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "SMA", "run_id": "run-html"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 10.0)],
        initial_cash=1000.0,
    )
    assert brief_path.exists()
    report_path = run_path / "report.html"
    assert report_path.exists()
    html = report_path.read_text()
    assert "Trading Report" in html and "Entries/Exits" in html

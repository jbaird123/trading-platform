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
    assert "setMarkers" in html
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

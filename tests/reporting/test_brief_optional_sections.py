from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief, save_run_brief


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


def test_generate_brief_omits_empty_optional_sections():
    b = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 1.0)],
        initial_cash=1000.0,
    )
    # Optional when empty: data_quality, checksums
    assert "data_quality" not in b
    assert "checksums" not in b or b["checksums"]


def test_save_run_brief_schema_validation_enabled(tmp_path):
    run_path = tmp_path / "u" / "r"
    out = save_run_brief(
        run_path,
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 1.0)],
        initial_cash=1000.0,
        validate_schema=True,
    )
    assert out.exists()

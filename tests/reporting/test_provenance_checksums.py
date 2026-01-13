# Validates: [JSON-11.24]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


def test_provenance_and_checksums_present_and_stable():
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
    inst = {"EURUSD": {"symbol": "EURUSD", "tick_size": 0.0001}}
    cfg = {"runs_dir": "runs", "log_level": "INFO"}
    b1 = generate_brief(
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
        meta={"run_id": "r1", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        instrument_definitions=inst,
        config_snapshot=cfg,
    )
    b2 = generate_brief(
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
        meta={"run_id": "r1", "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        instrument_definitions=inst,
        config_snapshot=cfg,
    )
    c1 = b1["checksums"]
    c2 = b2["checksums"]
    assert c1["instrument_defs_hash"] == c2["instrument_defs_hash"]
    assert c1["config_snapshot_hash"] == c2["config_snapshot_hash"]
    # Provenance keys present
    prov = b1["provenance"]
    assert "run_id" in prov and "strategy_name" in prov
    assert "app_version" in prov and "git_commit" in prov and "run_seed" in prov

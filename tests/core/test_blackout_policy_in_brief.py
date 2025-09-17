# Validates: [SYS-1.5.1], [JSON-11.21]
from __future__ import annotations

import json
from datetime import datetime, timedelta

from trading_platform.core.config import RunConfig
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


def test_blackout_policy_snapshot_appears_in_brief(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        blackout_utc=[("23:00", "01:00")],
        blackout_events=[
            {"start": datetime(2023, 1, 1, 11), "end": datetime(2023, 1, 1, 12)}
        ],
    )

    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[_t(datetime(2023, 1, 1), 1.0)],
        initial_cash=1000.0,
        config=cfg,
    )
    data = json.loads(brief_path.read_text())
    policy = data.get("blackout_policy")
    assert policy is not None
    assert policy.get("blackout_utc") == [["23:00", "01:00"]] or policy.get(
        "blackout_utc"
    ) == [("23:00", "01:00")]

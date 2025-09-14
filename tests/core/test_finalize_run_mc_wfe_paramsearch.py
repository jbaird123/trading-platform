from __future__ import annotations

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
        exit_price=1.0,
        side="long" if pnl >= 0 else "short",
        size=1.0,
        pnl=pnl,
    )


def test_finalize_run_populates_mc_wfe_paramsearch(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        runs_dir=tmp_path,
        monte_carlo={"trials": 50, "seed": 123},
        walk_forward={"window": 2, "step": 1},
        parameter_search={"grid": {"a": [1, 2]}, "objective": "total_pnl"},
    )
    out = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[
            _t(datetime(2024, 1, 1), 5.0),
            _t(datetime(2024, 1, 1, 1), -5.0),
            _t(datetime(2024, 1, 1, 2), 10.0),
        ],
        initial_cash=1000.0,
        config=cfg,
    )
    data = out.read_text()
    assert '"monte_carlo"' in data and '"walk_forward"' in data
    assert '"parameter_search"' in data

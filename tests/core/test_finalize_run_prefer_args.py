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
        side="long",
        size=1.0,
        pnl=pnl,
    )


def test_finalize_run_prefers_explicit_mc_over_config(tmp_path):
    run_path = tmp_path / "u" / "r"
    cfg = RunConfig(
        user_id="u",
        run_id="r",
        runs_dir=tmp_path,
        run_seed=42,
        log_level="INFO",
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
        monte_carlo={"trials": 1},
    )
    brief_path = finalize_run(
        run_path,
        meta={"strategy_name": "S", "run_id": "r"},
        params={},
        trades=[_t(datetime(2024, 1, 1), 1.0)],
        initial_cash=1000.0,
        config=cfg,
        monte_carlo={"mode": "test", "trials": 1},
    )
    data = brief_path.read_text()
    assert '"mode": "test"' in data

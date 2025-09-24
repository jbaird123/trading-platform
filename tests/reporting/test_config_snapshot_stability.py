# Validates: [JSON-11.24]
from __future__ import annotations

from datetime import datetime, timedelta

from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import generate_brief


def test_config_snapshot_hash_stable_for_same_runconfig():
    cfg = RunConfig(
        user_id="u",
        run_id="fixed",
        log_level="INFO",
        run_seed=42,
        initial_cash=10000.0,
        position_size=1.0,
        allow_flip_on_bar=False,
    )
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1) + timedelta(hours=1),
        entry_price=1.0,
        exit_price=0.9,
        side="long",
        size=1.0,
        pnl=-0.1,
    )
    b1 = generate_brief(
        meta={"run_id": cfg.run_id, "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        config_snapshot=cfg.model_dump(),
    )
    b2 = generate_brief(
        meta={"run_id": cfg.run_id, "strategy_name": "S"},
        params={},
        trades=[t],
        initial_cash=1000.0,
        config_snapshot=cfg.model_dump(),
    )
    assert (
        b1["checksums"]["config_snapshot_hash"]
        == b2["checksums"]["config_snapshot_hash"]
    )

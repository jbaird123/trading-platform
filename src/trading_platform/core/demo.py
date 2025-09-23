from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.csv_export import save_prices_csv


def generate_demo_run(user_id: str = "demo_user") -> Path:
    """Create a demo run with synthetic trades and write brief + HTML report.

    Returns the run directory path (runs/{user}/{run_id}).
    """
    cfg = RunConfig(
        user_id=user_id,
        run_seed=42,
        log_level="INFO",
        initial_cash=100000.0,
        allow_flip_on_bar=False,
        position_size=10000.0,
        instrument_definitions={
            "EURUSD": {
                "symbol": "EURUSD",
                "tick_size": 0.0001,
                "base_ccy": "EUR",
                "quote_ccy": "USD",
            }
        },
        fill_policy={"policy": "market"},
        tie_break_policy={"rule": "stop_then_tp"},
    )
    run_path = initialize_run(cfg)

    # Minimal instrument/policy snapshots are provided via RunConfig

    # Synthetic trades
    t0 = datetime(2023, 1, 1)
    trades = [
        Trade(
            symbol="EURUSD",
            entry_time=t0,
            exit_time=t0 + timedelta(hours=1),
            entry_price=1.0000,
            exit_price=1.0010,
            side="long",
            size=1.0,
            pnl=100.0,
            exit_reason="signal",
        ),
        Trade(
            symbol="EURUSD",
            entry_time=t0 + timedelta(days=1),
            exit_time=t0 + timedelta(days=1, hours=1),
            entry_price=1.0020,
            exit_price=1.0010,
            side="long",
            size=1.0,
            pnl=-100.0,
            exit_reason="stop-loss",
        ),
    ]
    # Minimal OHLCV for candlesticks
    from pandas import DataFrame, date_range

    idx = date_range(t0, periods=3, freq="h")
    df = DataFrame(
        {
            "open": [1.0, 1.001, 1.002],
            "high": [1.002, 1.003, 1.004],
            "low": [0.999, 1.000, 1.001],
            "close": [1.001, 1.002, 1.003],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    try:
        save_prices_csv(run_path / "prices.csv", df)
    except Exception:
        pass

    meta = {"strategy_name": "DemoStrategy", "run_id": cfg.run_id}
    params = {"fast": 10, "slow": 20}

    finalize_run(
        run_path,
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=1000.0,
        config=cfg,
    )

    return run_path


if __name__ == "__main__":
    p = generate_demo_run()
    print(f"Demo run created at: {p}")
    print(f"- Brief: {p / 'brief.json'}")
    print(f"- Report: {p / 'report.html'}")

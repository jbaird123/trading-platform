# Validates: [AI-F.2.1], [AI-F.2.2]
from __future__ import annotations

from datetime import datetime, timedelta

from pytest import approx

from trading_platform.core.robustness import (
    monte_carlo_summary,
    parameter_search,
    walk_forward_summary,
)
from trading_platform.portfolio.trade import Trade


def _trades() -> list[Trade]:
    t0 = datetime(2024, 1, 1)
    return [
        Trade(
            symbol="X",
            entry_time=t0 + timedelta(hours=i),
            exit_time=t0 + timedelta(hours=i + 1),
            entry_price=1.0,
            exit_price=1.0,
            side="long",
            size=1.0,
            pnl=float((i % 2) * 10 - 5),  # [-5, 5, -5, 5, ...]
        )
        for i in range(8)
    ]


def test_monte_carlo_summary_deterministic_with_seed():
    trades = _trades()
    mc = monte_carlo_summary(trades, initial_cash=1000.0, trials=100, seed=42)
    assert mc["trials"] == 100
    assert "final_equity" in mc and "total_pnl" in mc
    # Deterministic mean near 1000 due to symmetric pnl
    assert mc["final_equity"]["mean"] == approx(1000.0, abs=10.0)
    # Richer metrics should be present and numeric
    assert "max_drawdown" in mc and "win_rate" in mc
    assert isinstance(mc["max_drawdown"]["mean"], float)
    assert 0.0 <= mc["win_rate"]["mean"] <= 1.0


def test_walk_forward_summary_aggregates_oos():
    trades = _trades()
    wfe = walk_forward_summary(trades, window=3, step=2)
    assert wfe["oos_total_pnl"]["n_splits"] > 0


def test_parameter_search_grid_and_random():
    # objective: maximize a*x + b where a,b chosen from sets
    def eval_fn(p):
        return p["a"] * 2 + p["b"]

    out = parameter_search(
        grid={"a": [1, 2], "b": [0, 1]}, random_space=None, evaluate=eval_fn
    )
    assert out["top"]["params"] == {"a": 2, "b": 1}

    out2 = parameter_search(
        grid=None,
        random_space={"a": [0, 1], "b": [0, 1]},
        n_samples=5,
        seed=123,
        evaluate=eval_fn,
    )
    assert len(out2["results"]) == 5


def test_monte_carlo_block_bootstrap_mode():
    trades = _trades()
    mc = monte_carlo_summary(
        trades,
        initial_cash=1000.0,
        trials=50,
        seed=7,
        mode="block_bootstrap_trades",
        block_len=3,
    )
    assert mc["trials"] == 50
    assert "max_drawdown" in mc and "win_rate" in mc

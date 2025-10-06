# Validates: [AI-F.2.1], [AI-F.2.2]
from __future__ import annotations

from datetime import datetime

from trading_platform.core.robustness import (
    monte_carlo_summary,
    parameter_search,
    walk_forward_splits,
    walk_forward_summary,
)
from trading_platform.portfolio.trade import Trade


def test_mc_seed_and_identity_mode_and_trials_zero():
    t = Trade(
        symbol="X",
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 1, 1),
        entry_price=1.0,
        exit_price=2.0,
        side="long",
        size=1.0,
        pnl=1.0,
    )
    s1 = monte_carlo_summary(
        [t], initial_cash=100.0, trials=5, seed=42, mode="identity"
    )
    assert s1["mode"] == "identity" and s1["trials"] == 5
    s2 = monte_carlo_summary(
        [], initial_cash=100.0, trials=0, seed=None, mode="identity"
    )
    # Empty trades returns empty dict (fail-fast principle)
    assert s2 == {}


def test_walk_forward_splits_continue_and_summary_empty():
    idx = [1, 2, 3]
    splits = walk_forward_splits(idx, window=0, step=1)
    assert isinstance(splits, list)
    s = walk_forward_summary([], window=2, step=1)
    assert s["oos_total_pnl"]["mean"] == 0.0 and s["oos_total_pnl"]["n_splits"] == 0


def test_parameter_search_grid_and_random():
    res = parameter_search(
        grid={"a": [1]}, random_space=None, evaluate=lambda p: float(p["a"])
    )
    assert res["top"]["params"]["a"] == 1
    res2 = parameter_search(
        grid=None,
        random_space={"b": [1, 2]},
        n_samples=1,
        seed=1,
        evaluate=lambda p: float(p["b"]),
    )
    assert "top" in res2 and "results" in res2

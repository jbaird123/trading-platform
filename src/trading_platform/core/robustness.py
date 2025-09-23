from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Callable, cast

from trading_platform.portfolio.trade import Trade


def monte_carlo_summary(
    trades: list[Trade],
    *,
    initial_cash: float,
    trials: int = 1000,
    seed: int | None = None,
    mode: str = "bootstrap_trades",
    block_len: int | None = None,
) -> dict[str, Any]:
    """Compute simple MC stats by resampling trade PnLs.

    - mode 'bootstrap_trades': sample trade PnLs with replacement for same count.
    - Returns summary with mean, p05, p95 of final equity and pnl.
    """
    if seed is not None:
        random.seed(seed)
    pnls = [t.pnl for t in trades]
    n = max(1, len(pnls))
    finals: list[float] = []
    finals_pnl: list[float] = []
    dd_values: list[float] = []
    win_rates: list[float] = []

    def _block_bootstrap(values: list[float], m: int, b: int) -> list[float]:
        if b <= 0:
            b = 1
        out: list[float] = []
        max_start = max(0, m - b)
        while len(out) < m:
            start = random.randrange(max_start + 1) if max_start >= 0 else 0
            blk = values[start : start + b]
            if not blk:
                blk = values[:b]
            out.extend(blk)
        return out[:m]

    for _ in range(trials):
        if mode == "bootstrap_trades":
            sample = [pnls[random.randrange(n)] for _ in range(n)]
        elif mode == "block_bootstrap_trades":
            bl = int(block_len or max(1, int(n**0.5)))
            sample = _block_bootstrap(pnls, n, bl)
        else:  # fallback to identity
            sample = pnls
        total_pnl = float(sum(sample))
        finals_pnl.append(total_pnl)
        finals.append(initial_cash + total_pnl)
        # Compute max drawdown on equity path implied by sampled pnls
        eq = initial_cash
        peak = eq
        max_dd = 0.0
        wins = 0
        for p in sample:
            eq = eq + float(p)
            if eq > peak:
                peak = eq
            dd = max(0.0, peak - eq)
            if dd > max_dd:
                max_dd = dd
            if float(p) > 0.0:
                wins += 1
        dd_values.append(max_dd)
        win_rates.append(float(wins) / float(n) if n else 0.0)

    def _pct(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        vals = sorted(vals)
        k = (len(vals) - 1) * p
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        if f == c:
            return float(vals[f])
        d0 = vals[f] * (c - k)
        d1 = vals[c] * (k - f)
        return float(d0 + d1)

    return {
        "mode": mode,
        "trials": trials,
        "final_equity": {
            "mean": float(mean(finals)) if finals else initial_cash,
            "p05": _pct(finals, 0.05),
            "p95": _pct(finals, 0.95),
        },
        "total_pnl": {
            "mean": float(mean(finals_pnl)) if finals_pnl else 0.0,
            "p05": _pct(finals_pnl, 0.05),
            "p95": _pct(finals_pnl, 0.95),
        },
        "max_drawdown": {
            "mean": float(mean(dd_values)) if dd_values else 0.0,
            "p05": _pct(dd_values, 0.05),
            "p95": _pct(dd_values, 0.95),
        },
        "win_rate": {
            "mean": float(mean(win_rates)) if win_rates else 0.0,
            "p05": _pct(win_rates, 0.05),
            "p95": _pct(win_rates, 0.95),
        },
    }


@dataclass(frozen=True)
class WFESplit:
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any


def walk_forward_splits(
    index: Iterable[Any], *, window: int, step: int
) -> list[WFESplit]:
    idx = list(index)
    splits: list[WFESplit] = []
    for i in range(0, max(0, len(idx) - window), step):
        tr = idx[i : i + window]
        te = idx[i + window : i + window + step]
        if not tr or not te:
            continue
        splits.append(
            WFESplit(
                train_start=tr[0], train_end=tr[-1], test_start=te[0], test_end=te[-1]
            )
        )
    return splits


def walk_forward_summary(
    trades: list[Trade],
    *,
    window: int,
    step: int,
) -> dict[str, Any]:
    """Compute WFE summary by slicing trades into OOS windows by time.

    Uses trade entry_time as an index and computes OOS total_pnl per window.
    """
    trades_sorted = sorted(trades, key=lambda t: t.entry_time)
    idx = [t.entry_time for t in trades_sorted]
    splits = walk_forward_splits(idx, window=window, step=step)
    oos_results: list[float] = []
    for s in splits:
        oos = [
            t.pnl for t in trades_sorted if s.test_start <= t.entry_time <= s.test_end
        ]
        oos_results.append(float(sum(oos)))
    return {
        "splits": [s.__dict__ for s in splits],
        "oos_total_pnl": {
            "mean": float(mean(oos_results)) if oos_results else 0.0,
            "median": float(median(oos_results)) if oos_results else 0.0,
            "n_splits": len(oos_results),
        },
    }


def parameter_search(
    *,
    grid: dict[str, list[Any]] | None = None,
    random_space: dict[str, list[Any]] | None = None,
    n_samples: int | None = None,
    seed: int | None = None,
    evaluate: Callable[[dict[str, Any]], float],
) -> dict[str, Any]:
    """Parameter search returning top result.

    - Grid: cartesian product when provided.
    - Random: sample from search space when provided.
    - evaluate: returns a score (higher is better).
    """
    if seed is not None:
        random.seed(seed)
    candidates: list[dict[str, Any]] = []
    if grid:
        keys = list(grid.keys())
        lists = [grid[k] for k in keys]

        def _prod(
            prefix: dict[str, Any], rest_keys: list[str], rest_lists: list[list[Any]]
        ):
            if not rest_keys:
                candidates.append(prefix.copy())
                return
            k = rest_keys[0]
            for v in rest_lists[0]:
                prefix[k] = v
                _prod(prefix, rest_keys[1:], rest_lists[1:])

        _prod({}, keys, lists)
    if random_space and n_samples:
        keys = list(random_space.keys())
        for _ in range(n_samples):
            cand = {k: random.choice(random_space[k]) for k in keys}
            candidates.append(cand)

    results: list[dict[str, Any]] = [
        {"params": c, "score": float(evaluate(c))} for c in candidates
    ]
    results.sort(key=lambda r: cast(float, r["score"]), reverse=True)
    top = results[0] if results else {"params": {}, "score": 0.0}
    return {"top": top, "results": results}

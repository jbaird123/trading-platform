from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd
from trading_platform.portfolio.metrics import (
    calculate_equity_curve,
    calculate_win_rate,
)
from trading_platform.portfolio.trade import Trade


def _to_jsonable(obj: Any) -> Any:
    """Convert objects (dataclasses, datetimes) to JSON-serializable forms."""
    # asdict() only accepts dataclass instances, not classes.
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


# Reusable defaults to reduce duplication in assembled briefs
EMPTY_DISTRIBUTION = {
    "pnl_mean": 0.0,
    "pnl_median": 0.0,
    "pnl_std": 0.0,
    "p05": 0.0,
    "p95": 0.0,
}


def _empty_sections() -> dict[str, Any]:
    """Return fresh containers for always-present empty sections."""
    return {
        "activity": {},
        "timing_buckets": {},
        "costs": {},
        "exposure": {},
        "contrasts": {},
        "stop_tp_candidates": [],
        "parameter_search": {},
        "stationarity": {},
        "feature_analysis": {},
        "checksums": {},
    }


def _serialize_trade(t: Trade) -> dict[str, Any]:
    return {
        "symbol": t.symbol,
        "side": t.side,
        "size": t.size,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "pnl": t.pnl,
        "exit_reason": t.exit_reason,
        # Placeholders for future cost modeling (Task 14)
        "cost_breakdown": {
            "spread": 0.0,
            "commission": 0.0,
            "slippage": 0.0,
        },
    }


def compute_overall_performance(
    trades: list[Trade], initial_cash: float
) -> dict[str, Any]:
    equity_curve = calculate_equity_curve(trades, initial_cash)
    final_equity = equity_curve[-1][1] if equity_curve else initial_cash
    pnls = [t.pnl for t in trades]
    total_pnl = sum(pnls) if pnls else 0.0
    mean_pnl = (total_pnl / len(trades)) if trades else 0.0
    median_pnl = median(pnls) if pnls else 0.0
    by_side_total_pnl = {
        "long": sum(t.pnl for t in trades if t.side == "long"),
        "short": sum(t.pnl for t in trades if t.side == "short"),
    }
    return {
        "n_trades": len(trades),
        "total_pnl": total_pnl,
        "mean_pnl": mean_pnl,
        "median_pnl": median_pnl,
        "by_side_total_pnl": by_side_total_pnl,
        "win_rate": calculate_win_rate(trades),
        "initial_equity": initial_cash,
        "final_equity": final_equity,
    }


def compute_risk_snapshot(trades: list[Trade]) -> dict[str, Any]:
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    return {
        "win_rate": calculate_win_rate(trades),
        "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        "max_win": max(wins) if wins else 0.0,
        "max_loss": min(losses) if losses else 0.0,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return float(values[int(k)])
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return float(d0 + d1)


def compute_distribution(trades: list[Trade]) -> dict[str, Any]:
    pnls = [t.pnl for t in trades]
    if not pnls:
        return EMPTY_DISTRIBUTION
    n = len(pnls)
    mean_val = sum(pnls) / n
    median_val = median(pnls)
    var = sum((x - mean_val) ** 2 for x in pnls) / n
    std = var**0.5
    return {
        "pnl_mean": mean_val,
        "pnl_median": median_val,
        "pnl_std": std,
        "p05": _percentile(pnls, 0.05),
        "p95": _percentile(pnls, 0.95),
    }


def compute_streaks(trades: list[Trade]) -> dict[str, Any]:
    longest_win = 0
    longest_loss = 0
    current = 0
    current_sign = 0  # 1 win, -1 loss, 0 none
    for t in trades:
        if t.pnl > 0:
            sign = 1
        elif t.pnl < 0:
            sign = -1
        else:
            sign = 0
        if sign == 0:
            current = 0
            current_sign = 0
        elif sign == current_sign:
            current += 1
        else:
            current = 1
            current_sign = sign
        if current_sign == 1:
            longest_win = max(longest_win, current)
        elif current_sign == -1:
            longest_loss = max(longest_loss, current)
    return {
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
        "current_streak": current if current_sign != 0 else 0,
    }


def compute_equity_stats(trades: list[Trade], initial_cash: float) -> dict[str, Any]:
    ec = calculate_equity_curve(trades, initial_cash)
    max_peak = float("-inf")
    dd_curve: list[tuple[datetime, float]] = []
    max_dd = 0.0
    dd_duration = 0
    temp_duration = 0
    for ts, eq in ec:
        if eq > max_peak:
            max_peak = eq
            temp_duration = 0
        drawdown = max(0.0, max_peak - eq)
        dd_curve.append((ts, drawdown))
        if drawdown > 0:
            temp_duration += 1
            if drawdown > max_dd:
                max_dd = drawdown
                dd_duration = temp_duration
    equity_curve = [[ts.isoformat(), float(eq)] for ts, eq in ec]
    drawdown_curve = [[ts.isoformat(), float(dd)] for ts, dd in dd_curve]
    return {
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "max_drawdown": max_dd,
        "dd_duration_bars": dd_duration,
    }


def compute_costs_aggregate(trades: list[Trade]) -> dict[str, Any]:
    """Aggregate per-trade costs into totals/averages and breakdown sums.

    If a trade lacks cost fields, it contributes zeros.
    """
    if not trades:
        return {
            "total_costs": 0.0,
            "avg_cost_per_trade": 0.0,
            "breakdown": {"spread": 0.0, "commission": 0.0, "slippage": 0.0},
        }
    total = 0.0
    b_spread = 0.0
    b_comm = 0.0
    b_slip = 0.0
    for t in trades:
        total += getattr(t, "cost_currency", 0.0) or 0.0
        bd = getattr(t, "cost_breakdown", None) or {}
        b_spread += float(bd.get("spread", 0.0) or 0.0)
        b_comm += float(bd.get("commission", 0.0) or 0.0)
        b_slip += float(bd.get("slippage", 0.0) or 0.0)
    return {
        "total_costs": total,
        "avg_cost_per_trade": total / len(trades),
        "breakdown": {"spread": b_spread, "commission": b_comm, "slippage": b_slip},
    }


def _median_holding_secs(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    vals = [max(0.0, (t.exit_time - t.entry_time).total_seconds()) for t in trades]
    return float(median(vals))


def _compute_regimes(
    trades: list[Trade], regimes_at_entry: list[str] | None
) -> dict[str, Any]:
    if not regimes_at_entry or len(regimes_at_entry) != len(trades):
        return {}
    buckets: dict[str, list[float]] = {}
    for t, label in zip(trades, regimes_at_entry):
        buckets.setdefault(label, []).append(t.pnl)
    result: dict[str, Any] = {}
    for label, pnls in buckets.items():
        n = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        result[label] = {
            "n_trades": n,
            "total_pnl": float(sum(pnls)),
            "mean_pnl": float(sum(pnls) / n) if n else 0.0,
            "median_pnl": float(median(pnls)) if pnls else 0.0,
            "win_rate": (wins / n) if n else 0.0,
        }
    return result


def generate_brief(
    *,
    meta: dict[str, Any] | None,
    params: dict[str, Any] | None,
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    data_quality: dict[str, Any] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
    blackout_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a JSON brief from trades and metrics (incremental MVP)."""
    meta = meta or {}
    expected_params = [
        "fast",
        "slow",
        "stop_type",
        "stop_value",
        "tp_type",
        "tp_value",
        "trail_type",
        "trail_value",
        "atr_length",
        "tie_break",
    ]
    params_in = params or {}
    params = {k: params_in.get(k) for k in expected_params}
    performance = compute_overall_performance(trades, initial_cash)
    risk_snapshot = compute_risk_snapshot(trades)
    equity_stats = compute_equity_stats(trades, initial_cash)
    distribution = compute_distribution(trades)
    trades_json = []
    for t in trades:
        item = _serialize_trade(t)
        # Attach cost breakdown if available
        if getattr(t, "cost_breakdown", None) is not None:
            item["cost_breakdown"] = t.cost_breakdown
        trades_json.append(item)
    # Compute provenance/environment
    prov = _compute_provenance(trades, meta)
    env = _compute_environment()

    base = {
        "meta": _to_jsonable(meta),
        "params": _to_jsonable(params),
        # Canonical, instrument-agnostic sections
        "overall_performance": performance,
        "risk_snapshot": risk_snapshot,
        "equity_stats": equity_stats,
        "distribution": distribution,
        "streaks": compute_streaks(trades),
        "holding_time": {"median_secs": _median_holding_secs(trades)},
        "costs": compute_costs_aggregate(trades),
        "monte_carlo": _to_jsonable(monte_carlo or {}),
        "walk_forward": _to_jsonable(walk_forward or {}),
        "regimes": _compute_regimes(trades, regimes_at_entry),
        "data_quality": _to_jsonable(data_quality or {}),
        # Snapshots and placeholders (configurable)
        "instrument_definitions": _to_jsonable(instrument_definitions or {}),
        "cost_model": _to_jsonable(cost_model or {}),
        "fill_policy": _to_jsonable(fill_policy or {}),
        "tie_break_policy": _to_jsonable(tie_break_policy or {}),
        "blackout_policy": _to_jsonable(blackout_policy or {}),
        "environment": _to_jsonable(env),
        "provenance": _to_jsonable(prov),
        # Trades serialized with ISO datetimes
        "trades": trades_json,
    }
    placeholders = _empty_sections()
    placeholders.update(base)
    return placeholders


def save_brief(brief: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, indent=2))


def save_run_brief(
    run_path: Path,
    *,
    meta: dict[str, Any],
    params: dict[str, Any],
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    data_quality: dict[str, Any] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
    blackout_policy: dict[str, Any] | None = None,
) -> Path:
    """Generate and save a brief to `run_path/brief.json`.

    Returns the written path.
    """
    brief = generate_brief(
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=initial_cash,
        regimes_at_entry=regimes_at_entry,
        data_quality=data_quality,
        instrument_definitions=instrument_definitions,
        cost_model=cost_model,
        fill_policy=fill_policy,
        tie_break_policy=tie_break_policy,
        monte_carlo=monte_carlo,
        walk_forward=walk_forward,
        blackout_policy=blackout_policy,
    )
    out_path = run_path / "brief.json"
    save_brief(brief, out_path)
    return out_path


def compute_data_quality(df: pd.DataFrame) -> dict[str, Any]:
    """Return a simple data-quality snapshot for an OHLCV DataFrame.

    - Index monotonic increasing
    - Duplicate index count
    - NaN counts per column
    """
    result: dict[str, Any] = {}
    result["index_monotonic_increasing"] = bool(df.index.is_monotonic_increasing)
    result["duplicate_bars_count"] = int(df.index.duplicated().sum())
    nan_counts = {col: int(df[col].isna().sum()) for col in df.columns}
    result["nan_counts"] = nan_counts
    result["has_nans"] = any(nan_counts.values())
    return result


def _compute_environment() -> dict[str, Any]:
    tz = datetime.now().astimezone().tzinfo
    return {
        "python_version": sys.version.split(" ")[0],
        "platform": platform.platform(),
        "timezone": str(tz) if tz else None,
    }


def _compute_provenance(trades: list[Trade], meta: dict[str, Any]) -> dict[str, Any]:
    # Derive minimal provenance from trades and meta
    symbols = sorted({t.symbol for t in trades})
    data_start = min((t.entry_time for t in trades), default=None)
    data_end = max((t.exit_time for t in trades), default=None)
    meta = meta or {}
    return {
        "run_id": meta.get("run_id"),
        "strategy_name": meta.get("strategy_name"),
        "data_start": data_start.isoformat() if data_start else None,
        "data_end": data_end.isoformat() if data_end else None,
        "symbols": symbols,
    }

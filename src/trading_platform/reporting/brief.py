from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from trading_platform.portfolio.metrics import (
    calculate_equity_curve,
    calculate_win_rate,
)
from trading_platform.portfolio.trade import Trade


def _to_jsonable(obj: Any) -> Any:
    """Convert objects (dataclasses, datetimes) to JSON-serializable forms."""
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


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


def generate_brief(
    *,
    meta: dict[str, Any] | None,
    params: dict[str, Any] | None,
    trades: list[Trade],
    initial_cash: float,
) -> dict[str, Any]:
    """Assemble a minimal JSON brief from trades and metrics (MVP v1)."""
    meta = meta or {}
    # Normalize params to expected keys; instrument-agnostic core
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
    trades_json = [
        {
            "symbol": t.symbol,
            "side": t.side,
            "size": t.size,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat(),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "exit_reason": t.exit_reason,
        }
        for t in trades
    ]
    return {
        "meta": _to_jsonable(meta),
        "params": _to_jsonable(params),
        # Canonical, instrument-agnostic sections
        "overall_performance": performance,
        "risk_snapshot": risk_snapshot,
        "contrasts": {},
        "stop_tp_candidates": [],
        "monte_carlo": {},
        "walk_forward": {},
        "regimes": {},
        "parameter_search": {},
        "stationarity": {},
        "feature_analysis": {},
        # Trades serialized with ISO datetimes
        "trades": trades_json,
    }


def save_brief(brief: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, indent=2))

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
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
    net_pnl = final_equity - initial_cash
    return {
        "total_trades": len(trades),
        "win_rate": calculate_win_rate(trades),
        "net_pnl": net_pnl,
        "initial_equity": initial_cash,
        "final_equity": final_equity,
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
    params = params or {}
    performance = compute_overall_performance(trades, initial_cash)
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
        "overall_performance": performance,
        "trades": trades_json,
    }


def save_brief(brief: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, indent=2))

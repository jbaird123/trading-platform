from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from trading_platform.portfolio.trade import Trade


def save_trades_csv(path: Path, trades: list[Trade]) -> Path:
    """Save trades to CSV with enhanced fields.

    Columns: symbol, side, size, entry_time, exit_time, entry_price, exit_price,
    pnl, r_multiple, mfe_currency, mae_currency, bars_held, cost_currency,
    spread, commission, slippage
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "symbol",
        "side",
        "size",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "pnl",
        "r_multiple",
        "mfe_currency",
        "mae_currency",
        "bars_held",
        "cost_currency",
        "spread",
        "commission",
        "slippage",
    ]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for t in trades:
            bd: dict[str, Any] = t.cost_breakdown or {}
            row = {
                "symbol": t.symbol,
                "side": t.side,
                "size": t.size,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "r_multiple": getattr(t, "r_multiple", None),
                "mfe_currency": getattr(t, "mfe_currency", None),
                "mae_currency": getattr(t, "mae_currency", None),
                "bars_held": getattr(t, "bars_held", None),
                "cost_currency": getattr(t, "cost_currency", 0.0),
                "spread": bd.get("spread", 0.0),
                "commission": bd.get("commission", 0.0),
                "slippage": bd.get("slippage", 0.0),
            }
            w.writerow(row)
    return path

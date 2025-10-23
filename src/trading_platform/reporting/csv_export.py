from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import _normalize_trade_context


def save_trades_csv(path: Path, trades: list[Trade]) -> Path:
    """Save trades to CSV with enhanced fields including context_at_entry.

    Task 31: Flattens context_at_entry into columns with prefix 'ctx_'.
    For nested context like {'strategy_features': {'ema': 1.0}}, creates
    column 'ctx_strategy_ema' with value 1.0.

    Base columns: symbol, side, size, entry_time, exit_time, entry_price,
    exit_price, exit_reason, pnl, r_multiple, mfe_currency, mae_currency,
    bars_held, cost_currency, spread, commission, slippage

    Context columns: Dynamically added based on what's in context_at_entry
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Base columns (always present)
    base_cols = [
        "symbol",
        "side",
        "size",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "exit_reason",
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

    # Determine context columns by scanning all trades
    context_cols: set[str] = set()
    for t in trades:
        ctx = getattr(t, "context_at_entry", None)
        if ctx:
            normalized_ctx = _normalize_trade_context(ctx)
            if normalized_ctx:
                context_cols.update(_flatten_context_keys(normalized_ctx))

    # All columns = base + sorted context columns
    all_cols = base_cols + sorted(context_cols)

    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
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
                "exit_reason": getattr(t, "exit_reason", None),
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

            # Add context fields
            ctx = getattr(t, "context_at_entry", None)
            if ctx:
                normalized_ctx = _normalize_trade_context(ctx)
                if normalized_ctx:
                    row.update(_flatten_context(normalized_ctx))

            w.writerow(row)
    return path


def _flatten_context_keys(ctx: dict[str, Any], prefix: str = "ctx") -> set[str]:
    """Extract all flattened key names from nested context dict.

    Example: {'strategy_features': {'ema': 1.0}} -> {'ctx_strategy_ema'}
    """
    keys: set[str] = set()
    for k, v in ctx.items():
        if isinstance(v, dict):
            # Recurse into nested dict
            keys.update(_flatten_context_keys(v, prefix=f"{prefix}_{k}"))
        else:
            # Leaf value
            keys.add(f"{prefix}_{k}")
    return keys


def _flatten_context(ctx: dict[str, Any], prefix: str = "ctx") -> dict[str, Any]:
    """Flatten nested context dict into single-level dict with prefixed keys.

    Example: {'strategy_features': {'ema': 1.0}} -> {'ctx_strategy_ema': 1.0}
    """
    flat: dict[str, Any] = {}
    for k, v in ctx.items():
        if isinstance(v, dict):
            # Recurse into nested dict
            flat.update(_flatten_context(v, prefix=f"{prefix}_{k}"))
        else:
            # Leaf value
            flat[f"{prefix}_{k}"] = v
    return flat


def save_prices_csv(path: Path, df: pd.DataFrame) -> Path:
    """Persist OHLC to CSV for charts (time,open,high,low,close).

    Expects index to be datetime-like and columns: open, high, low, close.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["open", "high", "low", "close"]
    out = path
    df_to_write = df.copy()
    df_to_write = df_to_write[cols]
    df_to_write.to_csv(out, index_label="time")
    return out

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd

from trading_platform.core.costs import CostModel
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def simulate_counterfactual_fast(
    market_data: pd.DataFrame,
    strategy: CompiledStrategy | None = None,  # kept for signature parity
    *,
    start_index: int,
    side: str,
    entry_price: float,
    size: float,
    instrument: dict | None,
    cost_model: dict | None,
) -> dict[str, Any]:
    """Fast counterfactual: hold to end, compute extremes vectorially."""
    del strategy  # unused
    if start_index < 0 or start_index >= len(market_data):
        return {}

    idx = market_data.index
    last_idx = len(market_data) - 1

    exit_time = cast(datetime, idx[last_idx])
    exit_price = float(market_data.iloc[last_idx]["close"])

    window = market_data.iloc[start_index:]
    high_max = float(window["high"].max()) if "high" in window else entry_price
    low_min = float(window["low"].min()) if "low" in window else entry_price

    if side == "long":
        favorable = max(0.0, (high_max - entry_price) * size)
        adverse = max(0.0, (entry_price - low_min) * size)
        pnl_gross = (exit_price - entry_price) * size
    else:
        favorable = max(0.0, (entry_price - low_min) * size)
        adverse = max(0.0, (high_max - entry_price) * size)
        pnl_gross = (entry_price - exit_price) * size

    cm = CostModel.from_dict(cost_model)
    cost_entry, _ = cm.compute_entry_cost(
        size, price=entry_price, instrument=instrument
    )
    cost_exit, _ = cm.compute_exit_cost(size, price=exit_price, instrument=instrument)
    total_cost = float(cost_entry + cost_exit)

    pnl_net = float(pnl_gross) - total_cost
    bars_held = int(len(market_data) - start_index)

    return {
        "cf_exit_time": exit_time.isoformat(),
        "cf_exit_price": exit_price,
        "counterfactual_pnl": pnl_net,
        "cf_pnl_currency": pnl_net,
        "counterfactual_mfe_currency": float(favorable),
        "counterfactual_mae_currency": float(adverse),
        "cf_bars_held": bars_held,
        "cf_mode": "fast",
    }


def simulate_counterfactual_exact(
    market_data: pd.DataFrame,
    strategy: CompiledStrategy | None = None,  # kept for signature parity
    *,
    start_index: int,
    side: str,
    entry_price: float,
    size: float,
    instrument: dict | None,
    cost_model: dict | None,
    rem: RiskExitManager,
    symbol: str,
    data_handler: Any = None,
    bar_minutes: int | None = None,
) -> dict[str, Any]:
    """Exact counterfactual: bar-by-bar re-simulation with REM."""
    del strategy  # unused
    if start_index < 0 or start_index >= len(market_data):
        return {}

    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=0.0,
        instrument=instrument,
        cost_model=cost_model,
    )
    entry_time = cast(datetime, market_data.index[start_index])

    entry_bar = market_data.iloc[start_index]
    prior_bar = market_data.iloc[start_index - 1] if start_index > 0 else None
    initial_risk_ccy = None
    stop_price = None
    tp_price = None
    if rem is not None:
        stop_price = rem.calculate_initial_stop_price(
            entry_price=entry_price,
            side=side,
            entry_bar=entry_bar,
            signal_context={},
            prior_bar=prior_bar,
        )
        tp_price = rem.calculate_initial_take_profit_price(
            entry_price=entry_price,
            side=side,
            entry_bar=entry_bar,
            signal_context={},
            prior_bar=prior_bar,
        )
        if stop_price is not None:
            initial_risk_ccy = abs(entry_price - stop_price) * size

    pm.create_new_position(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        instrument=instrument,
        initial_risk_ccy=initial_risk_ccy,
        stop_loss=stop_price,
        take_profit=tp_price,
    )

    bars_touched = 0
    rem_exit = False
    for i in range(start_index, len(market_data)):
        cb = market_data.iloc[i]
        bars_touched += 1
        if pm.current_position:
            prior_bar = market_data.iloc[i - 1] if i > 0 else None
            rem_kwargs = {"data_handler": data_handler, "prior_bar": prior_bar}
            if bar_minutes is not None:
                rem_kwargs["bar_minutes"] = bar_minutes
            try:
                exit_details = rem.check_exits(
                    pm.current_position,
                    cb,
                    **rem_kwargs,
                )
            except TypeError:
                rem_kwargs.pop("bar_minutes", None)
                exit_details = rem.check_exits(
                    pm.current_position,
                    cb,
                    **rem_kwargs,
                )
            if exit_details:
                pm.close_position(
                    exit_price=exit_details["exit_price"],
                    exit_time=cast(datetime, cb.name),
                    exit_reason=exit_details["reason"],
                )
                rem_exit = True
                break

        if not pm.current_position:
            break

        pm.on_bar(current_bar=cb, current_signal=side)

    if pm.current_position:
        last_idx = len(market_data) - 1
        pm.close_position(
            exit_price=float(market_data.iloc[last_idx]["close"]),
            exit_time=cast(datetime, market_data.index[last_idx]),
        )
    if not pm.trades:
        return {}
    t = pm.trades[0]
    derived_bars_touched = int(max(1, t.bars_held or 0))
    bars_touched = int(max(bars_touched, derived_bars_touched))
    last_index = len(market_data) - 1
    exit_kind = "rem" if rem_exit else "end"
    return {
        "cf_exit_time": t.exit_time.isoformat(),
        "cf_exit_price": float(t.exit_price),
        "counterfactual_pnl": float(t.pnl),
        "cf_pnl_currency": float(t.pnl),
        "counterfactual_mfe_currency": float(t.mfe_currency or 0.0),
        "counterfactual_mae_currency": float(t.mae_currency or 0.0),
        "cf_bars_held": int(t.bars_held or 0),
        "cf_bars_touched": bars_touched,
        "cf_start_index": int(start_index),
        "cf_last_index": int(last_index),
        "cf_exit_kind": exit_kind,
        "cf_mode": "exact",
    }

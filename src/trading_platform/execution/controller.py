from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.strategy.yaml_strategy import compile_strategy


@dataclass(frozen=True)
class ControllerResult:
    orders: int
    logs: list[dict[str, Any]]


def reconcile(pm: PortfolioManager, adapter: OandaStubAdapter) -> list[str]:
    pm_pos = pm.current_position
    pm_side = pm_pos.side if pm_pos else None
    pm_size = float(pm_pos.size) if pm_pos else 0.0
    snap = adapter.account_snapshot()
    diffs: list[str] = []
    if snap.get("open_side") != pm_side:
        diffs.append("side_mismatch")
    size_val = snap.get("size")
    snap_size = float(size_val) if size_val is not None else 0.0
    if snap_size != pm_size:
        diffs.append("size_mismatch")
    return diffs


def run_live_controller(
    *,
    market_data: pd.DataFrame,
    strategy_cfg: dict[str, Any],
    adapter: OandaStubAdapter,
    pm: PortfolioManager,
    dry_run: bool = False,
    max_orders: int | None = None,
) -> ControllerResult:
    logs: list[dict[str, Any]] = []
    adapter.connect()
    logs.append({"event": "connect"})
    if dry_run:
        logs.append({"event": "dry_run", "ok": True})
        adapter.shutdown()
        logs.append({"event": "shutdown", "reason": "dry_run"})
        return ControllerResult(orders=0, logs=logs)

    strat = compile_strategy(strategy_cfg)
    signals = strat.generate_signals(market_data)
    current_state = "flat"
    placed = 0
    for i in range(len(market_data)):
        desired = str(signals.iloc[i])
        ts = market_data.index[i]
        px = float(market_data.iloc[i]["close"])
        if desired != current_state:
            # Try to align live state to desired state via market order
            side = desired
            if desired == "flat" and pm.current_position is None:
                # Nothing to flatten
                continue
            res = adapter.place_order(
                symbol="EURUSD", side=side, size=1.0, meta={"price": px, "time": ts}
            )
            logs.append(
                {
                    "event": "order",
                    "time": ts,
                    "side": side,
                    "status": res.status,
                    "message": res.message,
                }
            )
            if res.status == "accepted":
                placed += 1
                current_state = desired
                if max_orders is not None and placed >= max_orders:
                    logs.append({"event": "shutdown", "reason": "kill_switch"})
                    break
    # Reconcile once at the end
    diffs = reconcile(pm, adapter)
    logs.append({"event": "reconcile", "diffs": diffs})
    adapter.shutdown()
    logs.append({"event": "shutdown", "reason": "end"})
    return ControllerResult(orders=placed, logs=logs)

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.strategy import compile_strategy


@dataclass(frozen=True)
class ControllerResult:
    orders: int
    logs: list[dict[str, Any]]


@dataclass(frozen=True)
class ReconcileReport:
    severity: str  # info | warn | error
    deltas: dict[str, float]
    position_diffs: list[str]


def _realized_pnl_on(pm: PortfolioManager, d: date) -> float:
    return float(sum(t.pnl for t in pm.trades if t.exit_time.date() == d))


def reconcile_report(
    pm: PortfolioManager,
    adapter: OandaStubAdapter,
    *,
    mark_price: float | None = None,
    cash_tolerance: float = 1.0,
    size_tolerance: float = 0.0,
    pnl_tolerance: float = 1.0,
) -> ReconcileReport:
    pm_pos = pm.current_position
    pm_side = pm_pos.side if pm_pos else None
    pm_size = float(pm_pos.size) if pm_pos else 0.0
    pm_cash = float(pm.cash)
    pm_pnl_today = _realized_pnl_on(pm, datetime.now().date())
    pm_equity = pm_cash
    if mark_price is not None and pm_pos is not None:
        if pm_pos.side == "long":
            pm_equity += (float(mark_price) - float(pm_pos.entry_price)) * float(
                pm_pos.size
            )
        else:
            pm_equity += (float(pm_pos.entry_price) - float(mark_price)) * float(
                pm_pos.size
            )

    snap = adapter.account_snapshot()
    diffs: list[str] = []
    if snap.get("open_side") != pm_side:
        diffs.append("side_mismatch")
    size_val = snap.get("size")
    snap_size = float(size_val) if size_val is not None else 0.0
    if abs(snap_size - pm_size) > size_tolerance:
        diffs.append("size_mismatch")
    deltas: dict[str, float] = {}

    def _delta(key: str, pm_val: float) -> None:
        val = snap.get(key)
        snap_val = float(val) if val is not None else 0.0
        deltas[key] = snap_val - pm_val

    _delta("cash_balance", pm_cash)
    _delta("equity", pm_equity)
    _delta("realized_pnl_today", pm_pnl_today)

    sev = "info"
    if diffs:
        sev = "error"
    else:
        if (
            abs(deltas.get("cash_balance", 0.0)) > cash_tolerance
            or abs(deltas.get("equity", 0.0)) > cash_tolerance
            or abs(deltas.get("realized_pnl_today", 0.0)) > pnl_tolerance
        ):
            sev = "warn"
    return ReconcileReport(severity=sev, deltas=deltas, position_diffs=diffs)


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

    # Compute global features (for trade context enrichment)
    # Note: Live trading stub currently passes None for context, but we prepare
    # the infrastructure for when context is supported
    # This maintains parity with backtester architecture
    data_with_global_features = market_data
    global_features_dict: dict[str, pd.Series] = {}
    try:
        import logging

        from trading_platform.core.feature_resolver import resolve_global_features
        from trading_platform.strategy.features import compute_features

        logger = logging.getLogger(__name__)

        # Get execution timeframe (default to 1H)
        # In live trading without RunConfig, we default to 1H
        # which matches the most common trading timeframe
        execution_timeframe = "1H"

        # Resolve and compute global features
        resolved_features = resolve_global_features(execution_timeframe)
        global_features_list = [
            {
                "name": f.name,
                "type": f.type,
                "params": f.params,
                "source": f.source,
                "timeframe": f.timeframe,
            }
            for f in resolved_features
        ]

        if global_features_list:
            data_with_global_features = compute_features(
                market_data,
                global_features_list,
                strategy_parameters={},
            )
            # Store as dict for easy access
            from typing import cast

            for feature in global_features_list:
                fname = cast(str, feature["name"])
                if fname in data_with_global_features.columns:
                    global_features_dict[fname] = cast(
                        pd.Series, data_with_global_features[fname]
                    )

            logger.info(
                f"Computed {len(global_features_list)} global features for live trading"
            )
    except FileNotFoundError:
        pass  # global.yaml doesn't exist - proceed without global features
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(
            f"Failed to load global features in live trading: {e}"
        )
    placed = 0
    for i in range(len(market_data)):
        signal = signals.iloc[i]
        # Skip None commands (no action)
        if signal is None or (isinstance(signal, float) and pd.isna(signal)):
            continue

        # Extract command from Signal object or use as-is if string
        from trading_platform.core.signal import Signal

        if isinstance(signal, Signal):
            command = signal.command
        else:
            command = signal

        ts = market_data.index[i]
        px = float(market_data.iloc[i]["close"])

        # For exit commands when no position, skip
        if (
            command in ("exit_long", "exit_short", "flat")
            and pm.current_position is None
        ):
            continue

        res = adapter.place_order(
            symbol="EURUSD", side=command, size=1.0, meta={"price": px, "time": ts}
        )
        logs.append(
            {
                "event": "order",
                "time": ts,
                "side": command,
                "status": res.status,
                "message": res.message,
            }
        )
        if res.status == "accepted":
            placed += 1
            if max_orders is not None and placed >= max_orders:
                logs.append({"event": "shutdown", "reason": "kill_switch"})
                break
    # Reconcile once at the end (use last close as mark)
    mark_px = float(market_data.iloc[-1]["close"]) if len(market_data) else None
    report = reconcile_report(pm, adapter, mark_price=mark_px)
    logs.append({"event": "reconcile", "report": asdict(report)})
    adapter.shutdown()
    logs.append({"event": "shutdown", "reason": "end"})
    return ControllerResult(orders=placed, logs=logs)

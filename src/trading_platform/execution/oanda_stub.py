from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from trading_platform.execution.adapter_base import ExecutionAdapter, OrderResult
from trading_platform.portfolio.portfolio import PortfolioManager


class OandaStubAdapter(ExecutionAdapter):
    """A no-network stub that logs order attempts and can update PortfolioManager.

    - Accepts orders via `place_order` and returns `OrderResult`.
    - If a `PortfolioManager` is provided, it opens/closes positions using
      provided `meta` (expects `price` and optional `time`).
    """

    def __init__(
        self,
        pm: PortfolioManager | None = None,
        policy: Any | None = None,
        pm_limits: dict[str, int] | None = None,
        daily_loss_cap: float | None = None,
    ) -> None:
        self.pm = pm
        self.connected = False
        self._seq = 0
        self.events: list[dict[str, Any]] = []
        # Optional TradingWindowPolicy-like object with can_open(datetime) -> bool
        self.policy = policy
        self.pm_limits = pm_limits or {"max_open_long": 1, "max_open_short": 1}
        self.daily_loss_cap = daily_loss_cap

    def connect(self) -> None:
        self.connected = True

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        size: float,
        meta: dict[str, Any] | None = None,
    ) -> OrderResult:
        self._seq += 1
        order_id = f"stub-{self._seq}"
        meta = meta or {}
        price = float(meta.get("price", 0.0))
        ts = meta.get("time")
        when: datetime = ts if isinstance(ts, datetime) else datetime.now(timezone.utc)

        self.events.append(
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "size": size,
                "meta": meta,
            }
        )

        # Optional: reflect into PortfolioManager
        if self.pm is not None:
            # Block new opens if policy forbids at this time
            if side in {"long", "short"} and self.policy is not None:
                if not self.policy.can_open(when):
                    self.events.append({"order_id": order_id, "rejected": "blackout"})
                    return OrderResult(
                        order_id=order_id, status="rejected", message="blackout"
                    )
            # Enforce daily loss cap if provided
            if side in {"long", "short"} and self.daily_loss_cap:
                if self.pm.hit_daily_loss_cap(when, float(self.daily_loss_cap)):
                    self.events.append({"order_id": order_id, "rejected": "risk_cap"})
                    return OrderResult(
                        order_id=order_id, status="rejected", message="risk_cap"
                    )
            # Enforce simple directional cap: PM holds max one position
            if side in {"long", "short"} and self.pm.current_position:
                cap = (
                    self.pm_limits.get("max_open_long", 1)
                    if side == "long"
                    else self.pm_limits.get("max_open_short", 1)
                )
                open_ct = 1
                if open_ct >= cap and self.pm.current_position.side == side:
                    self.events.append(
                        {"order_id": order_id, "rejected": "position_cap"}
                    )
                    return OrderResult(
                        order_id=order_id,
                        status="rejected",
                        message="position_cap",
                    )
            if side in {"long", "short"}:
                if self.pm.current_position and self.pm.current_position.side != side:
                    self.pm.close_position(
                        exit_price=price, exit_time=when, exit_reason="flip"
                    )
                if not self.pm.current_position:
                    self.pm.create_new_position(
                        symbol=symbol,
                        side=side,
                        entry_price=price,
                        size=size,
                        entry_time=when,
                    )
            elif side == "flat" and self.pm.current_position:
                self.pm.close_position(
                    exit_price=price, exit_time=when, exit_reason="flat"
                )

        return OrderResult(order_id=order_id, status="accepted", message="stub")

    def shutdown(self) -> None:
        self.connected = False

    def account_snapshot(self) -> dict[str, float | str | None]:
        if self.pm is None or self.pm.current_position is None:
            return {"open_side": None, "size": 0.0}
        pos = self.pm.current_position
        return {"open_side": pos.side, "size": float(pos.size)}

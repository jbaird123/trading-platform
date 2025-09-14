from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CostModel:
    """Simple, extensible cost model.

    Definitions
    - "unit" means one unit of the position size passed to PortfolioManager.
      Examples:
        * Equities: unit = 1 share (commission per share)
        * Futures: unit = 1 contract (commission per contract)
        * Our BT examples: unit = whatever numeric size you pass (e.g., 10k)

    Fields
    - spread_per_unit: applied per side (entry and exit) as base-currency cost
    - slippage_per_unit: applied per side, base-currency
    - commission: supports multiple modes:
        * per_unit: value is base-currency per unit (e.g., $0.005/share)
        * per_trade_flat: value is base-currency per side (e.g., $1.00 per order)
        * bps_notional: value is basis points of notional (price*size*bps/10_000)

    All costs are applied per side (entry and exit) and returned in base currency.
    """

    spread_per_unit: float = 0.0
    slippage_per_unit: float = 0.0
    commission_type: str = "per_unit"  # one of: per_unit, per_trade_flat, bps_notional
    commission_value: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CostModel:
        d = d or {}
        # Back-compat: allow commission_per_unit in config
        comm = d.get("commission")
        c_type = comm.get("type") if isinstance(comm, dict) else None
        c_val = comm.get("value") if isinstance(comm, dict) else None
        if c_type is None and c_val is None:
            # fallback to legacy key
            c_type = "per_unit"
            c_val = d.get("commission_per_unit", 0.0)
        return cls(
            spread_per_unit=float(d.get("spread_per_unit", 0.0)),
            slippage_per_unit=float(d.get("slippage_per_unit", 0.0)),
            commission_type=str(c_type or "per_unit"),
            commission_value=float(c_val or 0.0),
        )

    def _commission_cost(self, size: float, price: float | None) -> float:
        if self.commission_type == "per_unit":
            return self.commission_value * size
        if self.commission_type == "per_trade_flat":
            return self.commission_value
        if self.commission_type == "bps_notional":
            notional = (price or 0.0) * size
            bps = self.commission_value / 10_000.0
            return notional * bps
        # Unknown type fallback to zero
        return 0.0

    def compute_entry_cost(
        self, size: float, price: float | None = None
    ) -> tuple[float, dict[str, float]]:
        """Cost charged at entry.

        Apply spread + commission + slippage at entry.
        """
        spread = self.spread_per_unit * size
        commission = self._commission_cost(size, price)
        slippage = self.slippage_per_unit * size
        total = spread + commission + slippage
        return total, {"spread": spread, "commission": commission, "slippage": slippage}

    def compute_exit_cost(
        self, size: float, price: float | None = None
    ) -> tuple[float, dict[str, float]]:
        """Cost charged at exit (same as entry for the simple model)."""
        return self.compute_entry_cost(size, price)

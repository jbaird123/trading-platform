from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CostModel:
    """Simple cost model with fixed per-unit costs.

    All values are expressed per unit of size, in base currency terms.
    """

    spread_per_unit: float = 0.0
    commission_per_unit: float = 0.0
    slippage_per_unit: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CostModel:
        d = d or {}
        return cls(
            spread_per_unit=float(d.get("spread_per_unit", 0.0)),
            commission_per_unit=float(d.get("commission_per_unit", 0.0)),
            slippage_per_unit=float(d.get("slippage_per_unit", 0.0)),
        )

    def compute_entry_cost(self, size: float) -> tuple[float, dict[str, float]]:
        """Cost charged at entry.

        For simplicity, apply full spread/commission/slippage at entry.
        """
        spread = self.spread_per_unit * size
        commission = self.commission_per_unit * size
        slippage = self.slippage_per_unit * size
        total = spread + commission + slippage
        return total, {"spread": spread, "commission": commission, "slippage": slippage}

    def compute_exit_cost(self, size: float) -> tuple[float, dict[str, float]]:
        """Cost charged at exit (same as entry for the simple model)."""
        return self.compute_entry_cost(size)

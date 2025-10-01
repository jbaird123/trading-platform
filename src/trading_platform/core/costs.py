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
    - spread_per_unit: bid-ask spread cost applied once at entry only
    - slippage_per_unit: applied per side (entry and exit), base-currency
    - commission: supports multiple modes:
        * per_unit: value is base-currency per unit (e.g., $0.005/share)
        * per_trade_flat: value is base-currency per side (e.g., $1.00 per order)
        * bps_notional: value is basis points of notional (price*size*bps/10_000)

    Spread is applied only at entry. Commission and slippage are applied per side.
    """

    spread_per_unit: float = 0.0
    slippage_per_unit: float = 0.0
    commission_type: str = "per_unit"  # one of: per_unit, per_trade_flat, bps_notional
    commission_value: float = 0.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CostModel:
        d = d or {}
        # Reject legacy/alias keys in greenfield to avoid ambiguity
        if "commission_per_unit" in d:
            raise ValueError(
                "Unsupported key 'commission_per_unit'. "
                "Use commission: {type: 'per_unit', value: <float>} instead."
            )

        # Safe float parser to satisfy type checker and handle None/str
        def _as_float(value: Any, default: float = 0.0) -> float:
            try:
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default

        comm = d.get("commission")
        if isinstance(comm, dict):
            c_type = str(comm.get("type", "per_unit"))
            c_val = _as_float(comm.get("value"), 0.0)
        else:
            c_type = "per_unit"
            c_val = 0.0
        return cls(
            spread_per_unit=_as_float(d.get("spread_per_unit"), 0.0),
            slippage_per_unit=_as_float(d.get("slippage_per_unit"), 0.0),
            commission_type=str(c_type),
            commission_value=float(c_val),
        )

    def _commission_cost(
        self, *, units: float, size: float, price: float | None
    ) -> float:
        if self.commission_type == "per_unit":
            return self.commission_value * units
        if self.commission_type == "per_trade_flat":
            return self.commission_value
        if self.commission_type == "bps_notional":
            notional = (price or 0.0) * size
            bps = self.commission_value / 10_000.0
            return notional * bps
        # Unknown type fallback to zero
        return 0.0

    def compute_entry_cost(
        self,
        size: float,
        price: float | None = None,
        instrument: dict[str, Any] | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Cost charged at entry.

        Apply spread + commission + slippage at entry.
        """
        units = effective_units(size, instrument)
        spread = self.spread_per_unit * units
        commission = self._commission_cost(units=units, size=size, price=price)
        slippage = self.slippage_per_unit * units
        total = spread + commission + slippage
        return total, {"spread": spread, "commission": commission, "slippage": slippage}

    def compute_exit_cost(
        self,
        size: float,
        price: float | None = None,
        instrument: dict[str, Any] | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Cost charged at exit.

        Spread is NOT applied at exit (already paid at entry).
        Only commission and slippage are charged.
        """
        units = effective_units(size, instrument)
        commission = self._commission_cost(units=units, size=size, price=price)
        slippage = self.slippage_per_unit * units
        total = commission + slippage
        return total, {"spread": 0.0, "commission": commission, "slippage": slippage}


def effective_units(size: float, instrument: dict[str, Any] | None) -> float:
    """Return size expressed in instrument-native units when possible.

    Examples
    - Equities (shares): lot_size=1 → effective_units(size)=size
    - Futures (contracts): lot_size=1 contract → effective_units=size
    - FX (lots): if lot_size=100000 and size is notional units (e.g., 10,000),
      effective_units = 10000 / 100000 = 0.1 lots.

    If instrument or lot_size is unspecified, returns the input size unchanged.
    """
    if not instrument:
        return size
    lot = instrument.get("lot_size")
    try:
        lot_val = float(lot) if lot is not None else None
    except (TypeError, ValueError):
        lot_val = None
    if lot_val and lot_val > 0:
        return size / lot_val
    return size

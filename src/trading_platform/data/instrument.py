from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InstrumentDefinition:
    """Minimal instrument metadata for snapshots and reporting.

    This is a scaffold for future expansion (tick_size, point_value, etc.).
    """

    symbol: str
    tick_size: float | None = None
    point_value: float | None = None
    base_ccy: str | None = None
    quote_ccy: str | None = None
    lot_size: float | None = None
    min_trade_unit: float | None = None
    commission_structure: dict[str, Any] | None = None
    spread_model: dict[str, Any] | None = None
    slippage_model: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict with None fields pruned."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

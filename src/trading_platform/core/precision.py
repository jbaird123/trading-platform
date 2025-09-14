from __future__ import annotations
# ruff: noqa: E402, I001  # Allow explanatory comments before imports; keep import block as-is

"""
Precision engines for arithmetic in the trading platform.

Why two engines?
- Backtesting favors speed and uses Python floats for performance (FloatEngine).
- Live trading favors exactness and repeatability; we use Decimal
  with instrument-aware quantization (DecimalEngine).

This keeps a single PortfolioManager implementation (shared by BT/EL) while
allowing each runtime to pick the appropriate numeric behavior.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Protocol


class PrecisionEngine(Protocol):
    def sub(self, a: float, b: float) -> object:  # numeric-like
        ...

    def mul(self, a: object, b: float) -> object: ...

    def to_float(self, a: object) -> float: ...


@dataclass(frozen=True)
class FloatEngine:
    """Fast float math for backtesting."""

    def sub(self, a: float, b: float) -> float:
        return a - b

    def mul(self, a: float, b: float) -> float:
        return a * b

    def to_float(self, a: float) -> float:
        return float(a)


@dataclass(frozen=True)
class DecimalEngine:
    """Exact arithmetic engine using Decimal.

    - tick_size: optional price increment (e.g., 0.0001). If provided, we use it
      to quantize intermediate values to reduce floating-point artifacts.
    - currency_dp: number of decimal places to quantize currency values to (2 by
      default, but callers can choose more precision if desired).
    """

    tick_size: float | None = None
    currency_dp: int = 6

    def __post_init__(self) -> None:
        # Increase precision to reduce rounding surprises during mul/sub
        getcontext().prec = max(getcontext().prec, 28)

    def _D(self, x: float | int | str) -> Decimal:
        # Use string conversion to avoid binary float artifacts
        return Decimal(str(x))

    def _quantize_price(self, d: Decimal) -> Decimal:
        if self.tick_size is None:
            return d
        step = self._D(self.tick_size)
        # Quantize to nearest multiple of step
        q = (d / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
        return q

    def _quantize_currency(self, d: Decimal) -> Decimal:
        fmt = (
            Decimal("1." + ("0" * self.currency_dp))
            if self.currency_dp > 0
            else Decimal("1")
        )
        return d.quantize(fmt, rounding=ROUND_HALF_UP)

    def sub(self, a: float, b: float) -> Decimal:
        res = self._D(a) - self._D(b)
        return self._quantize_price(res)

    def mul(self, a: Decimal, b: float) -> Decimal:
        res = a * self._D(b)
        return self._quantize_currency(res)

    def to_float(self, a: Decimal) -> float:
        return float(self._quantize_currency(a))

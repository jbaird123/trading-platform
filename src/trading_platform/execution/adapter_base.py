from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OrderResult:
    """Minimal result for an order submission."""

    order_id: str
    status: str  # e.g., "accepted", "rejected"
    message: str | None = None


class ExecutionAdapter(ABC):
    """Minimal interface for a live execution adapter (MVP).

    Implementations should be side-effect-free in dry runs and avoid
    network calls in tests. All parameters are deliberately simple to keep
    the boundary stable while we iterate.
    """

    @abstractmethod
    def connect(self) -> None:
        """Initialize any required resources (no network in stubs)."""

    @abstractmethod
    def place_order(
        self, *, symbol: str, side: str, size: float, meta: dict[str, Any] | None = None
    ) -> OrderResult:
        """Submit a market order request and return a minimal result."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources / close sessions (no-op in stubs)."""

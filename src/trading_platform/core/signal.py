"""Signal data structure for strategy commands with context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    """
    Represents a trading signal with command and contextual data.

    Attributes:
        command: Trading command (e.g., 'enter_long', 'exit_short')
        context: Dictionary of contextual data provided by strategy
    """

    command: str
    context: dict[str, Any] = field(default_factory=dict)

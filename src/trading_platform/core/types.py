"""Core type definitions for the trading platform."""

from typing import Any, Literal, Protocol, runtime_checkable

# Signal command types for strategy output
SignalCommand = Literal["enter_long", "enter_short", "exit_long", "exit_short", None]


@runtime_checkable
class BarData(Protocol):
    """Protocol capturing the minimal interface of a bar-like mapping."""

    name: Any

    def __contains__(self, key: str) -> bool: ...

    def __getitem__(self, key: str) -> Any: ...

    def get(self, key: str, default: Any | None = None) -> Any: ...

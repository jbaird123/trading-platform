"""Core type definitions for the trading platform."""

from typing import Literal

# Signal command types for strategy output
SignalCommand = Literal["enter_long", "enter_short", "exit_long", "exit_short", None]
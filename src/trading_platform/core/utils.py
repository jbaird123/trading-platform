from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


def gen_run_id(prefix: str = "run") -> str:
    # e.g., run_20250908_142500_utc
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
    return f"{prefix}_{ts}"


def get_logger(name: str = "trading") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        log.setLevel(logging.INFO)
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    return log


def normalize_symbol(symbol: str) -> str:
    """
    Validates and uppercases symbol. Rejects symbols with separators.

    Args:
        symbol: Symbol string to validate (e.g., 'EURUSD', 'eurusd')

    Returns:
        Uppercased symbol string

    Raises:
        ValueError: If symbol contains non-alphanumeric characters

    Examples:
        >>> normalize_symbol("EURUSD")  # Valid
        'EURUSD'
        >>> normalize_symbol("eurusd")  # Valid (uppercased)
        'EURUSD'
        >>> normalize_symbol("EUR/USD")  # Invalid
        ValueError: Invalid symbol 'EUR/USD'. Symbol must contain only letters...
    """
    normalized = symbol.strip().upper()
    if not normalized.isalnum():
        raise ValueError(
            f"Invalid symbol '{symbol}'. Symbol must contain only letters and "
            f"numbers (e.g., 'EURUSD', not 'EUR_USD' or 'EUR/USD')"
        )
    return normalized

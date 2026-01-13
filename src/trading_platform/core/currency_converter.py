"""Currency conversion service for P&L normalization.

Converts P&L from native (quote) currency to reference currency at trade close time.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from trading_platform.data.handler import DataHandler

logger = logging.getLogger(__name__)

# Mapping of quote currency to conversion pair needed for USD
# Format: quote_ccy -> (pair_symbol, is_direct)
# is_direct=True means divide by rate (USD is base), False means multiply (USD is quote)
_USD_CONVERSION_PAIRS: dict[str, tuple[str, bool]] = {
    "USD": ("", True),  # No conversion needed
    "JPY": ("USDJPY", True),  # Divide by USDJPY rate
    "CAD": ("USDCAD", True),  # Divide by USDCAD rate
    "CHF": ("USDCHF", True),  # Divide by USDCHF rate
    "GBP": ("GBPUSD", False),  # Multiply by GBPUSD rate
    "EUR": ("EURUSD", False),  # Multiply by EURUSD rate
    "AUD": ("AUDUSD", False),  # Multiply by AUDUSD rate
    "NZD": ("NZDUSD", False),  # Multiply by NZDUSD rate
}


class CurrencyConverter:
    """Service for converting amounts between currencies at specific timestamps.

    This service handles P&L conversion from the native (quote) currency of a
    trading pair to a reference currency (typically USD).

    For USD/XXX pairs (like USDJPY), the exit price of the trade itself can be
    used for conversion. For cross pairs (like EURJPY), we need to load the
    conversion pair data (USDJPY) to get the rate.

    Example:
        converter = CurrencyConverter(data_root=paths.RAW_DATA_DIR)
        converter.preload_for_symbol("USDJPY")

        # Convert JPY P&L to USD at trade exit time
        pnl_usd = converter.convert(
            amount=1000.0,  # 1000 JPY profit
            from_ccy="JPY",
            timestamp=exit_time,
            exit_price=150.0,  # USDJPY exit rate
            symbol="USDJPY",
        )
        # Returns ~6.67 USD
    """

    def __init__(
        self,
        reference_currency: str = "USD",
        data_root: Path | str | None = None,
    ) -> None:
        """Initialize the currency converter.

        Args:
            reference_currency: Target currency for conversion (default: USD)
            data_root: Root directory for market data files
        """
        self.reference_currency = reference_currency
        self._data_root = Path(data_root) if data_root else None
        self._rate_cache: dict[str, pd.DataFrame] = {}
        self._handlers: dict[str, DataHandler] = {}

    def convert(
        self,
        amount: float,
        from_ccy: str,
        timestamp: datetime,
        exit_price: float | None = None,
        symbol: str | None = None,
    ) -> float:
        """Convert amount from source currency to reference currency.

        Args:
            amount: Amount in source currency
            from_ccy: Source currency code (e.g., "JPY", "USD")
            timestamp: Time of conversion (for rate lookup)
            exit_price: Exit price of the trade (used when symbol is USD/XXX)
            symbol: Original trading symbol (optimization for USD/XXX pairs)

        Returns:
            Amount converted to reference currency
        """
        if self.reference_currency != "USD":
            raise NotImplementedError(
                f"Only USD reference currency is currently supported, "
                f"got {self.reference_currency}"
            )

        # No conversion needed if already in reference currency
        if from_ccy == "USD":
            return amount

        # For USD/XXX pairs (USDJPY, USDCAD, USDCHF), we can use exit_price directly
        # This avoids needing to load additional data
        if symbol and symbol.startswith("USD") and exit_price and exit_price > 0:
            return amount / exit_price

        # For other pairs, we need to look up the conversion rate
        conversion_info = _USD_CONVERSION_PAIRS.get(from_ccy)
        if conversion_info is None:
            logger.warning(
                f"No conversion pair defined for {from_ccy} -> USD. "
                f"Returning unconverted amount."
            )
            return amount

        pair_symbol, is_direct = conversion_info
        if not pair_symbol:
            # USD -> USD, no conversion
            return amount

        rate = self._get_rate(pair_symbol, timestamp)
        if rate is None:
            logger.warning(
                f"Could not get {pair_symbol} rate at {timestamp}. "
                f"Returning unconverted amount."
            )
            return amount

        if is_direct:
            # USD is base (USDJPY): divide by rate
            return amount / rate
        else:
            # USD is quote (GBPUSD): multiply by rate
            return amount * rate

    def _get_rate(self, pair_symbol: str, timestamp: datetime) -> float | None:
        """Get conversion rate for a currency pair at a timestamp.

        Uses forward-fill to get the most recent rate at or before the timestamp.
        """
        # Load data if not cached
        if pair_symbol not in self._rate_cache:
            self._load_pair_data(pair_symbol)

        if pair_symbol not in self._rate_cache:
            return None

        df = self._rate_cache[pair_symbol]
        if df.empty:
            return None

        # Find closest rate at or before timestamp
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        mask = df.index <= ts

        if not mask.any():
            # Timestamp is before all data - use first available
            return float(df.iloc[0]["close"])

        return float(df.loc[mask].iloc[-1]["close"])

    def _load_pair_data(self, symbol: str) -> None:
        """Lazy-load price data for a conversion pair."""
        if self._data_root is None:
            logger.debug(f"No data_root configured, cannot load {symbol}")
            return

        from trading_platform.data.handler import DataHandler
        from trading_platform.data.instrument import get_instrument_definition

        try:
            instrument = get_instrument_definition(symbol)
            handler = DataHandler(
                symbol=symbol,
                data_root=self._data_root,
                instrument=instrument,
            )
            data = handler.get_data()
            if data is not None and not data.empty:
                self._rate_cache[symbol] = data
                self._handlers[symbol] = handler
                logger.debug(f"Loaded {len(data)} rows for {symbol} conversion data")
        except FileNotFoundError:
            logger.warning(f"No data available for conversion pair {symbol}")
        except Exception as e:
            logger.warning(f"Failed to load {symbol} for currency conversion: {e}")

    def preload_for_symbol(self, symbol: str) -> None:
        """Preload conversion data needed for a trading symbol.

        Call this before running a backtest to ensure conversion data is ready.
        For USD/XXX pairs, no preloading is needed since we use exit_price.
        For cross pairs like EURJPY, this will load USDJPY data.

        Args:
            symbol: The trading symbol (e.g., "USDJPY", "EURJPY")
        """
        from trading_platform.data.instrument import get_instrument_definition

        try:
            inst = get_instrument_definition(symbol)
            quote_ccy = inst.quote_ccy

            if not quote_ccy or quote_ccy == "USD":
                # No conversion needed for USD-quoted pairs
                return

            # Check if this is a USD/XXX pair - we use exit_price directly
            if symbol.startswith("USD"):
                return

            # For cross pairs, preload the conversion pair
            conversion_info = _USD_CONVERSION_PAIRS.get(quote_ccy)
            if conversion_info:
                pair_symbol, _ = conversion_info
                if pair_symbol and pair_symbol not in self._rate_cache:
                    logger.info(f"Preloading {pair_symbol} for {symbol} P&L conversion")
                    self._load_pair_data(pair_symbol)

        except Exception as e:
            logger.warning(f"Failed to preload conversion data for {symbol}: {e}")

    def get_quote_currency(self, symbol: str) -> str:
        """Get the quote currency for a symbol.

        Args:
            symbol: Trading symbol (e.g., "USDJPY")

        Returns:
            Quote currency code (e.g., "JPY"), or "USD" as fallback
        """
        from trading_platform.data.instrument import get_instrument_definition

        try:
            inst = get_instrument_definition(symbol)
            return inst.quote_ccy or "USD"
        except Exception:
            return "USD"


def convert_pnl_to_usd(
    pnl_native: float,
    quote_ccy: str,
    exit_price: float,
    symbol: str,
) -> float:
    """Simple helper for USD/XXX pair conversion without full converter.

    This is a lightweight function for cases where we know the pair is USD/XXX
    and don't need the full CurrencyConverter machinery.

    Args:
        pnl_native: P&L in native (quote) currency
        quote_ccy: Quote currency code
        exit_price: Exit price of the trade
        symbol: Trading symbol

    Returns:
        P&L converted to USD
    """
    if quote_ccy == "USD":
        return pnl_native

    # For USD/XXX pairs, divide by exit rate
    if symbol.startswith("USD") and exit_price > 0:
        return pnl_native / exit_price

    # For other pairs, return unconverted (caller should use full converter)
    return pnl_native

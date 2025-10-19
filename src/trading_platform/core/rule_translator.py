"""Rule Translator - Converts native terms (pips, points) to canonical price offsets.

This module implements [SYS-1.3.3]: User-facing components may allow inputs in
native terms (pips, points), but these must be translated into the canonical model.
"""

from __future__ import annotations

from trading_platform.data.instrument import InstrumentDefinition


class RuleTranslator:
    """Translates native terms to canonical price offsets."""

    def __init__(self, instrument: InstrumentDefinition):
        """Initialize the translator with instrument metadata.

        Args:
            instrument: Instrument definition containing pip_location and other metadata
        """
        self.instrument = instrument

    def pips_to_price_offset(self, pips: float) -> float:
        """Convert a pip value to canonical price offset.

        Args:
            pips: Number of pips (e.g., 20 pips)

        Returns:
            Canonical price offset (e.g., 0.0020 for EUR/USD, 0.20 for USD/JPY)

        Example:
            >>> # For EUR/USD (pip_location=0.0001)
            >>> translator = RuleTranslator(eurusd_instrument)
            >>> translator.pips_to_price_offset(20)  # 20 pips
            0.0020

            >>> # For USD/JPY (pip_location=0.01)
            >>> translator = RuleTranslator(usdjpy_instrument)
            >>> translator.pips_to_price_offset(20)  # 20 pips
            0.20
        """
        assert self.instrument.pip_location is not None
        result: float = float(pips * self.instrument.pip_location)
        return result

    def price_offset_to_pips(self, price_offset: float) -> float:
        """Convert a canonical price offset to pips.

        Args:
            price_offset: Canonical price offset (e.g., 0.0020)

        Returns:
            Number of pips

        Example:
            >>> # For EUR/USD (pip_location=0.0001)
            >>> translator = RuleTranslator(eurusd_instrument)
            >>> translator.price_offset_to_pips(0.0020)
            20.0

            >>> # For USD/JPY (pip_location=0.01)
            >>> translator = RuleTranslator(usdjpy_instrument)
            >>> translator.price_offset_to_pips(0.20)
            20.0
        """
        assert self.instrument.pip_location is not None
        result: float = float(price_offset / self.instrument.pip_location)
        return result

    def points_to_price_offset(self, points: float) -> float:
        """Convert points to canonical price offset.

        Args:
            points: Number of points (instrument-specific definition)

        Returns:
            Canonical price offset

        Note:
            For most forex, 1 point = 1 pip. This method exists for extensibility
            to futures/other instruments where points differ from pips.
        """
        # For forex, points == pips
        return self.pips_to_price_offset(points)

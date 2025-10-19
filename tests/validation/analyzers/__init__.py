"""Analyzer registry for different exit mechanism types.

This module provides a pluggable registry system for analyzers that detect
and categorize trade exit discrepancies between platform and TradingView.

Usage:
    # Register a new analyzer
    @register_analyzer("my_mechanism")
    class MyAnalyzer(AmbiguityAnalyzer):
        ...

    # Create analyzer from strategy metadata
    metadata = {"exit_mechanisms": ["trailing_stop"], ...}
    analyzer = create_analyzer_for_strategy(metadata)
"""

from typing import Dict, Type

from tests.validation.ambiguity_analyzer import (
    AmbiguityAnalyzer,
    CompositeAmbiguityAnalyzer,
)

# Registry mapping exit mechanism types to analyzer classes
ANALYZER_REGISTRY: Dict[str, Type[AmbiguityAnalyzer]] = {}


def register_analyzer(exit_mechanism: str):
    """Decorator to register an analyzer for an exit mechanism type.

    Args:
        exit_mechanism: Name of exit mechanism (e.g., "trailing_stop", "indicator_stop")

    Example:
        >>> @register_analyzer("trailing_stop")
        >>> class TrailingStopAnalyzer(AmbiguityAnalyzer):
        ...     pass
    """

    def decorator(cls: Type[AmbiguityAnalyzer]):
        ANALYZER_REGISTRY[exit_mechanism] = cls
        return cls

    return decorator


def create_analyzer_for_strategy(metadata: dict) -> AmbiguityAnalyzer:
    """Factory to create analyzer(s) based on strategy metadata.

    Reads metadata.json fields like:
    - "exit_mechanisms": ["trailing_stop", "take_profit"]
    - "trailing_stop_pips": 20
    - "take_profit_pips": 15
    - "indicator_stop_type": "atr"
    - etc.

    Returns appropriate analyzer (single or composite).

    Args:
        metadata: Strategy metadata dictionary from metadata.json

    Returns:
        AmbiguityAnalyzer instance (single or composite)

    Raises:
        ValueError: If exit_mechanisms missing or no analyzer registered

    Example:
        >>> metadata = {
        ...     "exit_mechanisms": ["trailing_stop"],
        ...     "trailing_stop_pips": 20
        ... }
        >>> analyzer = create_analyzer_for_strategy(metadata)
        >>> type(analyzer).__name__
        'TrailingStopAnalyzer'
    """
    exit_mechanisms = metadata.get("exit_mechanisms", [])

    if not exit_mechanisms:
        raise ValueError(
            "metadata.json must specify 'exit_mechanisms' list. "
            f"Available keys: {list(metadata.keys())}"
        )

    analyzers = []
    for mechanism in exit_mechanisms:
        analyzer_class = ANALYZER_REGISTRY.get(mechanism)
        if not analyzer_class:
            raise ValueError(
                f"No analyzer registered for exit mechanism '{mechanism}'. "
                f"Available mechanisms: {list(ANALYZER_REGISTRY.keys())}"
            )

        # Create analyzer with metadata
        analyzer = analyzer_class.from_metadata(metadata)  # type: ignore[attr-defined]
        analyzers.append(analyzer)

    if len(analyzers) == 1:
        return analyzers[0]  # type: ignore[no-any-return]
    else:
        return CompositeAmbiguityAnalyzer(analyzers)

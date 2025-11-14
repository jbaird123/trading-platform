"""CLI wrapper for recommendation regeneration helper."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    generate_threshold_recommendations as _generator,
)

if __name__ == "__main__":  # pragma: no cover
    _generator.main()

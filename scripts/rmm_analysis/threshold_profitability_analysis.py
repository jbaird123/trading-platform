"""CLI wrapper for threshold profitability analysis."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    threshold_profitability_analysis as _analysis,
)

if __name__ == "__main__":  # pragma: no cover
    _analysis.main()

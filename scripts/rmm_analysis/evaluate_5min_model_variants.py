"""CLI wrapper for evaluating 5min profitability models."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    evaluate_5min_model_variants as _evaluate_5min,
)

if __name__ == "__main__":  # pragma: no cover
    _evaluate_5min.main()

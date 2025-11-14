"""CLI wrapper for selected-group profitability training."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    train_profitability_selected_groups as _train,
)

if __name__ == "__main__":  # pragma: no cover
    _train.main()

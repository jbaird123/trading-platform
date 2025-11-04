"""CLI wrapper for threshold sweep utilities."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    threshold_sweep_selected_groups as _sweep,
)

if __name__ == "__main__":  # pragma: no cover
    _sweep.main()

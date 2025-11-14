"""CLI wrapper for RMM optimization workflow."""

from __future__ import annotations

from trading_platform.rmm_analysis import run_rmm_optimization as _optimizer

if __name__ == "__main__":  # pragma: no cover
    _optimizer.main()

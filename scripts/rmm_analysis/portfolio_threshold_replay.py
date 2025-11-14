"""CLI wrapper for portfolio threshold replay."""

from __future__ import annotations

from trading_platform.rmm_analysis import portfolio_threshold_replay as _replay

if __name__ == "__main__":  # pragma: no cover
    _replay.main()

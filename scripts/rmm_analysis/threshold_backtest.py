"""CLI wrapper for threshold backtest utilities."""

from __future__ import annotations

from trading_platform.rmm_analysis import threshold_backtest as _backtest

if __name__ == "__main__":  # pragma: no cover
    _backtest.main()

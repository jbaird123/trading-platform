# Coverage gaps for portfolio/metrics.py - missing line 27 (empty trades list)
from __future__ import annotations

from trading_platform.portfolio.metrics import calculate_win_rate


def test_metrics_calculate_win_rate_empty_trades():
    """Test calculate_win_rate with empty trades list (line 27)."""
    # Empty trades list should return 0.0
    result = calculate_win_rate([])

    # Should return 0.0 when no trades - tests line 27
    assert result == 0.0

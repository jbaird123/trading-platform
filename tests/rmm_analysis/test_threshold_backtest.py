"""Tests for threshold backtest helpers."""

from __future__ import annotations

import numpy as np
from trading_platform.rmm_analysis.threshold_backtest import _compute_metrics


def test_compute_metrics_with_values() -> None:
    values = np.array([1.0, -0.5, 0.5])
    metrics = _compute_metrics(values)
    assert metrics["count"] == 3.0
    assert metrics["mean_r_multiple"] == 1.0 / 3.0
    assert metrics["win_rate"] == 2.0 / 3.0


def test_compute_metrics_empty() -> None:
    metrics = _compute_metrics(np.array([]))
    assert metrics["count"] == 0.0
    assert np.isnan(metrics["mean_r_multiple"])

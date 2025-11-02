"""Tests for threshold profitability analysis helpers."""

from __future__ import annotations

import numpy as np

from scripts.rmm_analysis.threshold_profitability_analysis import (
    compute_profitability_metrics,
)


def test_compute_profitability_metrics_handles_selection() -> None:
    y_true = np.array([-1.0, 0.5, 1.2, -0.2, 0.8])
    probabilities = np.array([0.2, 0.6, 0.9, 0.3, 0.7])
    metrics = compute_profitability_metrics(y_true, probabilities, [0.5])
    assert len(metrics) == 1
    result = metrics[0]
    assert result["selected_trades"] == 3.0
    assert result["selected_fraction"] == 3.0 / 5.0
    assert result["win_rate_selected"] > 0.0

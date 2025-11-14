"""Tests for threshold sweep utilities."""

from __future__ import annotations

import numpy as np
from trading_platform.rmm_analysis.threshold_sweep_selected_groups import (
    evaluate_thresholds,
)


def test_evaluate_thresholds_computes_metrics() -> None:
    y_true = np.array([-1.0, 0.5, 0.7, -0.3, 1.2])
    proba = np.array([0.2, 0.6, 0.8, 0.4, 0.9])
    result = evaluate_thresholds(y_true, proba, [0.5])
    assert len(result) == 1
    metrics = result[0]
    assert metrics["threshold"] == 0.5
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["accuracy"] <= 1.0

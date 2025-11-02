"""Tests for threshold equity curve helpers."""

from __future__ import annotations

import numpy as np

from scripts.rmm_analysis.threshold_equity_curve import equity_curve


def test_equity_curve_masks_and_cumsum() -> None:
    r_values = np.array([1.0, -0.5, 0.5, 2.0])
    probabilities = np.array([0.8, 0.4, 0.9, 0.2])
    included, baseline, filtered = equity_curve(r_values, probabilities, 0.7)
    assert included.tolist() == [True, False, True, False]
    assert baseline.tolist() == [1.0, 0.5, 1.0, 3.0]
    assert filtered.tolist() == [1.0, 1.0, 1.5, 1.5]

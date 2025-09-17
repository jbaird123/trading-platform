# Validates: [JSON-11.13]
from __future__ import annotations

from datetime import datetime, timedelta

from pytest import approx
from trading_platform.reporting.brief import generate_brief


def test_exposure_metrics_from_curve():
    t0 = datetime(2024, 1, 1, 0, 0)
    curve = [
        (t0, 0.0),
        (t0 + timedelta(hours=1), 1000.0),
        (t0 + timedelta(hours=2), 500.0),
    ]
    brief = generate_brief(
        meta={"run_id": "r", "strategy_name": "S"},
        params={},
        trades=[],
        initial_cash=1000.0,
        exposure_curve=curve,
    )
    exposure = brief["exposure"]
    assert exposure["average_gross_exposure"] == approx((0.0 + 1000.0 + 500.0) / 3)
    assert exposure["peak_gross_exposure"] == approx(1000.0)

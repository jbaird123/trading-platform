# Validates: [JSON-11.13]
from __future__ import annotations

from datetime import datetime, timedelta

from pytest import approx
from trading_platform.reporting.brief import generate_brief


def _default_bar_timestamps(
    start: datetime = datetime(2023, 1, 1), periods: int = 500, freq_hours: int = 1
) -> list[datetime]:
    return [start + timedelta(hours=i * freq_hours) for i in range(periods)]


DEFAULT_BAR_TIMESTAMPS = _default_bar_timestamps()


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
        bar_timestamps=DEFAULT_BAR_TIMESTAMPS,
    )
    exposure = brief["exposure"]
    assert exposure["average_gross_exposure"] == approx((0.0 + 1000.0 + 500.0) / 3)
    assert exposure["peak_gross_exposure"] == approx(1000.0)

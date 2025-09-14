from __future__ import annotations

from trading_platform.core.precision import DecimalEngine, FloatEngine


def test_float_engine_basic_arithmetic():
    e = FloatEngine()
    diff = e.sub(1.0025, 1.0000)
    val = e.mul(diff, 10000)
    assert abs(e.to_float(val) - 25.0) < 1e-9


def test_decimal_engine_quantizes_and_matches_simple_case():
    e = DecimalEngine(tick_size=0.0001, currency_dp=6)
    # 0.0025 difference at tick_size 0.0001 → exact 25.0 for 10k units
    diff = e.sub(1.0025, 1.0000)
    val = e.mul(diff, 10000)
    assert abs(e.to_float(val) - 25.0) < 1e-9


def test_decimal_engine_tick_quantization_rounds_half_up():
    e = DecimalEngine(tick_size=0.0001, currency_dp=6)
    # Half a tick should round half-up to one tick
    diff_half_tick = e.sub(1.00005, 1.00000)  # 0.00005 → 0.0001
    val = e.mul(diff_half_tick, 10000)
    assert abs(e.to_float(val) - 1.0) < 1e-9

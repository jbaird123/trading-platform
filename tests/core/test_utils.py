# Validates: [SYS-1.2.4], [SYS-1.3.5]
from __future__ import annotations

import logging

import pytest
from trading_platform.core.utils import gen_run_id, get_logger, normalize_symbol


def test_gen_run_id_contains_prefix_and_utc_suffix():
    rid = gen_run_id(prefix="test")
    assert rid.startswith("test_")
    assert rid.endswith("_utc")


def test_get_logger_adds_handler_once():
    name = "tp.test.logger.unique"
    # First call should add a handler
    log1 = get_logger(name)
    assert isinstance(log1, logging.Logger)
    assert len(log1.handlers) >= 1
    first_count = len(log1.handlers)

    # Second call should reuse the same logger without adding extra handlers
    log2 = get_logger(name)
    assert log2 is log1
    assert len(log2.handlers) == first_count


def test_get_logger_with_level():
    name = "tp.test.logger.level"
    log = get_logger(name)
    log.setLevel(logging.DEBUG)
    assert log.level == logging.DEBUG
    # Reset level for other tests
    log.setLevel(logging.INFO)


@pytest.mark.parametrize(
    "input_symbol,expected_output",
    [
        ("EUR/USD", "EURUSD"),
        ("EUR_USD", "EURUSD"),
        ("eur-jpy", "EURJPY"),
        ("SPY", "SPY"),
        ("EURUSD", "EURUSD"),
        ("gbp/usd", "GBPUSD"),
        ("USD-CAD", "USDCAD"),
        ("usd_jpy", "USDJPY"),
        ("NZD/USD", "NZDUSD"),
        ("AUD_JPY", "AUDJPY"),
        ("EUR.GBP", "EURGBP"),  # Test dot separator
        ("ESZ24", "ESZ24"),  # Test numbers preserved
        ("CLV24/NYM", "CLV24NYM"),  # Test numbers with separators
        ("BTC-USD", "BTCUSD"),
        ("eth_usdt", "ETHUSDT"),
    ],
)
def test_normalize_symbol(input_symbol: str, expected_output: str) -> None:
    """Test normalize_symbol function with comprehensive input variations."""
    result = normalize_symbol(input_symbol)
    assert result == expected_output

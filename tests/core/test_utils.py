# Validates: [SYS-1.2.4]
from __future__ import annotations

import logging

from trading_platform.core.utils import gen_run_id, get_logger


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

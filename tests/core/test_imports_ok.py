# Validates: [SYS-1.2.3]
from __future__ import annotations

import importlib


def test_import_top_level_packages():
    # Smoke import to detect circular import failures early
    for mod in [
        "trading_platform.core",
        "trading_platform.data",
        "trading_platform.strategy",
        "trading_platform.backtester",
        "trading_platform.portfolio",
        "trading_platform.execution",
        "trading_platform.reporting",
    ]:
        importlib.import_module(mod)

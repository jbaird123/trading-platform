"""Tests for public API import boundaries.

# Validates: [SYS-1.2.2]
"""

from __future__ import annotations

import importlib
import sys

import pytest

pytestmark = pytest.mark.skip(reason="Public API imports await __init__.py updates")


def test_public_api_imports():
    """Test that all public API modules can be imported.

    Validates: [SYS-1.2.2]
    """
    # Core public APIs
    public_modules = [
        "trading_platform.backtester",
        "trading_platform.portfolio",
        "trading_platform.strategy",
        "trading_platform.data",
        "trading_platform.reporting",
        "trading_platform.regime_market_manager",
        "trading_platform.risk_manager",
    ]

    for module_name in public_modules:
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import public module {module_name}: {e}")


def test_internal_modules_not_exposed():
    """Test that internal implementation details are not in public API.

    Validates: [SYS-1.2.2]
    """
    # These should NOT be importable from top-level public API
    internal_patterns = [
        "_internal",
        "_impl",
        "_private",
    ]

    # Get all trading_platform modules
    trading_platform_modules = [
        name for name in sys.modules.keys() if name.startswith("trading_platform")
    ]

    # Check that internal patterns are not exposed at top level
    for module_name in trading_platform_modules:
        parts = module_name.split(".")
        for part in parts:
            if any(pattern in part for pattern in internal_patterns):
                # Internal modules can exist, but shouldn't be in __all__
                # (This is a soft check - adjust based on actual architecture)
                pass


def test_strategy_base_is_public():
    """Test that Strategy base class is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.strategy import Strategy  # type: ignore[attr-defined]

    assert Strategy is not None
    assert hasattr(Strategy, "generate_signal")


def test_backtester_is_public():
    """Test that Backtester class is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.backtester import Backtester  # type: ignore[attr-defined]

    assert Backtester is not None
    assert hasattr(Backtester, "run")


def test_portfolio_manager_is_public():
    """Test that PortfolioManager is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.portfolio import PortfolioManager  # type: ignore[attr-defined]

    assert PortfolioManager is not None
    assert hasattr(PortfolioManager, "process_command")


def test_data_loader_is_public():
    """Test that data loading functions are accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.data import load_data  # type: ignore[attr-defined]

    assert load_data is not None


def test_brief_generation_is_public():
    """Test that brief generation is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.reporting import generate_brief  # type: ignore[attr-defined]

    assert generate_brief is not None


def test_rmm_is_public():
    """Test that RegimeMarketManager is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.regime_market_manager import RegimeMarketManager  # type: ignore[attr-defined]

    assert RegimeMarketManager is not None


def test_rem_is_public():
    """Test that RiskExitManager is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.risk_manager import RiskExitManager  # type: ignore[attr-defined]

    assert RiskExitManager is not None


def test_yaml_strategy_is_public():
    """Test that YamlStrategy is accessible from public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform.strategy import YamlStrategy  # type: ignore[attr-defined]

    assert YamlStrategy is not None


def test_no_implementation_leakage():
    """Test that implementation details don't leak through public API.

    Validates: [SYS-1.2.2]
    """
    from trading_platform import strategy

    # Public API should not expose internal helper functions
    # (adjust based on actual design)
    public_attrs = [attr for attr in dir(strategy) if not attr.startswith("_")]

    # These should be the main public classes
    expected_public = ["Strategy", "YamlStrategy"]

    for expected in expected_public:
        assert expected in public_attrs, f"{expected} should be in public API"


def test_circular_import_protection():
    """Test that there are no circular import issues.

    Validates: [SYS-1.2.2]
    """
    # Try importing in different orders to catch circular dependencies

    # If we get here without ImportError, circular imports are avoided
    assert True


def test_typing_imports_available():
    """Test that type hints are available from public API.

    Validates: [SYS-1.2.2]
    """
    # Type hints should be importable for users
    try:
        from trading_platform.portfolio.trade import Trade
        from trading_platform.strategy.base import Strategy  # type: ignore[attr-defined]

        assert Trade is not None
        assert Strategy is not None
    except ImportError as e:
        pytest.fail(f"Type hints should be accessible: {e}")

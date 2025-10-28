"""Shared fixtures for backtester tests."""
import pytest


@pytest.fixture(autouse=True)
def mock_global_features_for_backtester_tests(monkeypatch, request):
    """Mock global features to return empty list for backtester unit tests.

    Skip mocking for tests that explicitly need global features (e.g., contextual feature tests).
    """
    # Skip mocking for test_contextual_features.py tests
    if "test_contextual_features" in request.node.nodeid:
        return

    def mock_resolve(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "trading_platform.core.feature_resolver.resolve_global_features",
        mock_resolve
    )

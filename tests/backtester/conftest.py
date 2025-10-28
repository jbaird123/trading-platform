"""Shared fixtures for backtester tests."""
import pytest


@pytest.fixture(autouse=True)
def mock_global_features_for_backtester_tests(monkeypatch, request):
    """Mock global features to return empty list for backtester unit tests.

    Skip mocking for tests that explicitly need global features (e.g., contextual feature tests).
    """
    # Skip mocking for tests that require real global features
    if any(
        name in request.node.nodeid
        for name in ("test_contextual_features", "test_warmup_guards")
    ):
        return

    def mock_resolve(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "trading_platform.core.feature_resolver.resolve_global_features",
        mock_resolve
    )

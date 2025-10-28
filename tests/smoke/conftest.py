"""Shared fixtures for smoke tests."""
import pytest


@pytest.fixture(autouse=True)
def mock_global_features_for_smoke_tests(monkeypatch, request):
    """Mock global features to return empty list for smoke tests.

    Skip mocking for tests that explicitly need global features.
    """
    # Skip mocking for contextual features test
    if "contextual_features" in request.node.nodeid:
        return

    def mock_resolve(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "trading_platform.core.feature_resolver.resolve_global_features",
        mock_resolve
    )

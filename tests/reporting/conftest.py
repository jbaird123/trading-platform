"""Shared fixtures for reporting tests."""

import pytest


@pytest.fixture(autouse=True)
def mock_global_features_for_reporting_tests(monkeypatch):
    """Mock global features to return empty list for reporting tests."""

    def mock_resolve(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "trading_platform.core.feature_resolver.resolve_global_features", mock_resolve
    )

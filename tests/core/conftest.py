import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", action="store_true", help="update golden master files"
    )


@pytest.fixture(autouse=True)
def mock_global_features_for_core_tests(monkeypatch):
    """Mock global features to return empty list for core tests.

    This prevents core orchestration tests from failing due to insufficient
    warmup for global features. These tests focus on core functionality
    like parameter sweeps, monte carlo, etc., not on validating global features.
    """
    def mock_resolve(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "trading_platform.core.feature_resolver.resolve_global_features",
        mock_resolve
    )

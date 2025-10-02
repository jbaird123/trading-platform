"""Tests for execution layer API connectivity and retry logic.

# Validates: [EL-8.4]
"""

from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest


def test_api_connection_retry_on_network_error():
    """Test that API calls retry on network errors.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_retry

    mock_api = Mock()
    # Fail twice, then succeed
    mock_api.get_account.side_effect = [
        ConnectionError("Network error"),
        ConnectionError("Network error"),
        {"balance": 10000, "positions": []}
    ]

    result = execute_with_retry(mock_api.get_account, max_retries=3, retry_delay=0.01)

    assert result == {"balance": 10000, "positions": []}
    assert mock_api.get_account.call_count == 3


def test_api_connection_exponential_backoff():
    """Test that retries use exponential backoff.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_retry

    mock_api = Mock()
    mock_api.get_account.side_effect = [
        ConnectionError("Error 1"),
        ConnectionError("Error 2"),
        {"balance": 10000}
    ]

    start = time.perf_counter()
    execute_with_retry(
        mock_api.get_account,
        max_retries=3,
        retry_delay=0.01,
        backoff_factor=2
    )
    elapsed = time.perf_counter() - start

    # With exponential backoff: 0.01 + 0.02 = 0.03 seconds minimum
    # Allow some overhead
    assert elapsed >= 0.025


def test_api_connection_max_retries_exceeded():
    """Test that max retries limit is enforced.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_retry

    mock_api = Mock()
    mock_api.get_account.side_effect = ConnectionError("Persistent error")

    with pytest.raises(ConnectionError):
        execute_with_retry(mock_api.get_account, max_retries=3, retry_delay=0.01)

    assert mock_api.get_account.call_count == 3


def test_api_connection_timeout_handling():
    """Test that API timeouts are handled gracefully.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_retry

    mock_api = Mock()
    mock_api.get_account.side_effect = [
        TimeoutError("Request timeout"),
        {"balance": 10000}
    ]

    result = execute_with_retry(mock_api.get_account, max_retries=3, retry_delay=0.01)

    assert result == {"balance": 10000}
    assert mock_api.get_account.call_count == 2


def test_api_connection_different_error_types():
    """Test handling of different error types.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_retry

    mock_api = Mock()

    # Non-retryable error (e.g., authentication)
    mock_api.authenticate.side_effect = PermissionError("Invalid API key")

    with pytest.raises(PermissionError):
        # Should not retry on authentication errors
        execute_with_retry(
            mock_api.authenticate,
            max_retries=3,
            retry_delay=0.01,
            retryable_errors=(ConnectionError, TimeoutError)
        )

    # Should fail immediately
    assert mock_api.authenticate.call_count == 1


def test_api_connection_circuit_breaker():
    """Test circuit breaker pattern to prevent cascading failures.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import CircuitBreaker

    cb = CircuitBreaker(failure_threshold=3, timeout=1.0)
    mock_api = Mock()
    mock_api.get_account.side_effect = ConnectionError("Service down")

    # Trigger circuit breaker with 3 failures
    for _ in range(3):
        try:
            cb.call(mock_api.get_account)
        except ConnectionError:
            pass

    # Circuit should be open now
    assert cb.is_open()

    # Further calls should fail immediately without trying
    with pytest.raises(Exception, match="Circuit breaker is open"):
        cb.call(mock_api.get_account)


def test_api_connection_health_check():
    """Test API health check before critical operations.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import check_api_health

    mock_api = Mock()
    mock_api.ping.return_value = {"status": "ok", "latency_ms": 50}

    is_healthy = check_api_health(mock_api)

    assert is_healthy is True
    assert mock_api.ping.called


def test_api_connection_fallback_endpoint():
    """Test fallback to backup endpoint on primary failure.

    Validates: [EL-8.4]
    """
    from trading_platform.execution.controller import execute_with_fallback

    primary_api = Mock()
    fallback_api = Mock()

    primary_api.get_account.side_effect = ConnectionError("Primary down")
    fallback_api.get_account.return_value = {"balance": 10000}

    result = execute_with_fallback(
        lambda: primary_api.get_account(),
        lambda: fallback_api.get_account()
    )

    assert result == {"balance": 10000}
    assert primary_api.get_account.called
    assert fallback_api.get_account.called


# Mock implementations for testing
def execute_with_retry(func, max_retries=3, retry_delay=0.1, backoff_factor=1, retryable_errors=None):
    """Mock retry logic."""
    if retryable_errors is None:
        retryable_errors = (ConnectionError, TimeoutError)

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if not isinstance(e, retryable_errors):
                raise
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (backoff_factor ** attempt))


class CircuitBreaker:
    """Mock circuit breaker implementation."""

    def __init__(self, failure_threshold, timeout):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self._open = False

    def call(self, func):
        if self._open:
            raise Exception("Circuit breaker is open")

        try:
            result = func()
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self._open = True
            raise

    def is_open(self):
        return self._open


def check_api_health(api):
    """Mock health check."""
    try:
        response = api.ping()
        return response.get("status") == "ok"
    except Exception:
        return False


def execute_with_fallback(primary_func, fallback_func):
    """Mock fallback execution."""
    try:
        return primary_func()
    except Exception:
        return fallback_func()

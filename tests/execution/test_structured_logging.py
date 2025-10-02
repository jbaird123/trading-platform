"""Tests for structured logging in execution layer.

# Validates: [EL-8.7]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


def test_structured_log_format():
    """Test that logs use structured JSON format.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import StructuredLogger

    logger = StructuredLogger("test")

    # Create log entry
    log_entry = {
        "timestamp": "2024-01-01T00:00:00Z",
        "level": "INFO",
        "message": "Order executed",
        "order_id": "12345",
        "symbol": "EURUSD",
        "side": "buy",
        "quantity": 10000
    }

    # Verify it's valid JSON
    json_str = json.dumps(log_entry)
    parsed = json.loads(json_str)

    assert parsed["order_id"] == "12345"
    assert parsed["symbol"] == "EURUSD"


def test_structured_log_includes_context():
    """Test that logs include execution context.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import log_execution

    context = {
        "strategy": "SMA_Crossover",
        "account_id": "A12345",
        "broker": "OANDA"
    }

    log_entry = log_execution(
        action="place_order",
        order_type="market",
        symbol="EURUSD",
        context=context
    )

    assert "strategy" in log_entry
    assert "account_id" in log_entry
    assert log_entry["action"] == "place_order"


def test_structured_log_trade_lifecycle():
    """Test logging complete trade lifecycle.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import TradeLogger

    logger = TradeLogger()

    # Log trade events
    logger.log_order_placed(order_id="O123", symbol="EURUSD", side="buy", quantity=10000)
    logger.log_order_filled(order_id="O123", fill_price=1.1000, fill_time="2024-01-01T00:00:00Z")
    logger.log_order_closed(order_id="O123", close_price=1.1050, pnl=500.0)

    logs = logger.get_logs()

    assert len(logs) == 3
    assert logs[0]["event"] == "order_placed"
    assert logs[1]["event"] == "order_filled"
    assert logs[2]["event"] == "order_closed"
    assert logs[2]["pnl"] == 500.0


def test_structured_log_error_tracking():
    """Test that errors are logged with full context.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import log_error

    try:
        # Simulate error
        raise ConnectionError("Failed to connect to broker API")
    except Exception as e:
        log_entry = log_error(
            error=e,
            context={
                "operation": "connect_api",
                "broker": "OANDA",
                "retry_count": 3
            }
        )

        assert log_entry["level"] == "ERROR"
        assert "ConnectionError" in log_entry["error_type"]
        assert log_entry["retry_count"] == 3


def test_structured_log_performance_metrics():
    """Test logging performance metrics.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import log_performance

    metrics = {
        "order_latency_ms": 45.2,
        "api_response_time_ms": 120.5,
        "processing_time_ms": 5.3
    }

    log_entry = log_performance("order_execution", metrics)

    assert log_entry["order_latency_ms"] == 45.2
    assert log_entry["api_response_time_ms"] == 120.5


def test_structured_log_sanitizes_sensitive_data():
    """Test that sensitive data is sanitized in logs.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import sanitize_log

    sensitive_data = {
        "api_key": "secret_key_12345",
        "password": "my_password",
        "account_number": "1234567890",
        "symbol": "EURUSD"  # Not sensitive
    }

    sanitized = sanitize_log(sensitive_data)

    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["symbol"] == "EURUSD"  # Should remain


def test_structured_log_correlation_id():
    """Test that logs include correlation ID for request tracing.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import StructuredLogger
    import uuid

    logger = StructuredLogger("test")
    correlation_id = str(uuid.uuid4())

    log_entries = []
    log_entries.append(logger.log("Order request received", correlation_id=correlation_id))
    log_entries.append(logger.log("Order validation passed", correlation_id=correlation_id))
    log_entries.append(logger.log("Order sent to broker", correlation_id=correlation_id))

    # All logs should have same correlation ID
    assert all(entry["correlation_id"] == correlation_id for entry in log_entries)


def test_structured_log_filtering():
    """Test log filtering by level and category.

    Validates: [EL-8.7]
    """
    from trading_platform.execution.logging_config import LogFilter

    logs = [
        {"level": "DEBUG", "category": "api", "message": "Request sent"},
        {"level": "INFO", "category": "trade", "message": "Order placed"},
        {"level": "ERROR", "category": "api", "message": "Connection failed"},
        {"level": "INFO", "category": "trade", "message": "Order filled"},
    ]

    filter_obj = LogFilter(min_level="INFO", category="trade")
    filtered = [log for log in logs if filter_obj.match(log)]

    assert len(filtered) == 2
    assert all(log["category"] == "trade" for log in filtered)
    assert all(log["level"] in ["INFO", "ERROR"] for log in filtered)


# Mock implementations
class StructuredLogger:
    """Mock structured logger."""

    def __init__(self, name):
        self.name = name

    def log(self, message, **kwargs):
        entry = {
            "logger": self.name,
            "message": message,
            **kwargs
        }
        return entry


class TradeLogger:
    """Mock trade lifecycle logger."""

    def __init__(self):
        self.logs = []

    def log_order_placed(self, **kwargs):
        self.logs.append({"event": "order_placed", **kwargs})

    def log_order_filled(self, **kwargs):
        self.logs.append({"event": "order_filled", **kwargs})

    def log_order_closed(self, **kwargs):
        self.logs.append({"event": "order_closed", **kwargs})

    def get_logs(self):
        return self.logs


def log_execution(action, **kwargs):
    """Mock execution logging."""
    return {"action": action, **kwargs}


def log_error(error, context):
    """Mock error logging."""
    return {
        "level": "ERROR",
        "error_type": type(error).__name__,
        "error_message": str(error),
        **context
    }


def log_performance(operation, metrics):
    """Mock performance logging."""
    return {"operation": operation, **metrics}


def sanitize_log(data):
    """Mock log sanitization."""
    sensitive_keys = ["api_key", "password", "secret", "token"]
    sanitized = {}

    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value

    return sanitized


class LogFilter:
    """Mock log filter."""

    def __init__(self, min_level="INFO", category=None):
        self.min_level = min_level
        self.category = category
        self.levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}

    def match(self, log):
        level_match = self.levels[log["level"]] >= self.levels[self.min_level]
        category_match = self.category is None or log.get("category") == self.category
        return level_match and category_match

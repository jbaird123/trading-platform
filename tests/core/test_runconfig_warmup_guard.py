"""Ensure deprecated warmup configuration is rejected."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from trading_platform.core.config import RunConfig


def test_runconfig_rejects_warmup_bars() -> None:
    """RunConfig should reject legacy warmup_bars field."""
    with pytest.raises(ValidationError):
        RunConfig.model_validate(
            {
                "run_id": "invalid_warmup",
                "instrument": {"symbol": "EURUSD"},
                "warmup_bars": 5,
            }
        )

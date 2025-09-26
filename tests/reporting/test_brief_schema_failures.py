from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting import brief


def _trade() -> Trade:
    now = datetime(2024, 1, 1, 0, 0, 0)
    return Trade(
        symbol="EURUSD",
        entry_time=now,
        exit_time=now + timedelta(hours=1),
        entry_price=1.0,
        exit_price=1.0,
        side="long",
        size=1.0,
        pnl=1.0,
        exit_reason="test",
    )


def test_generate_brief_raises_when_schema_description_missing(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: "{}")

    with pytest.raises(ValueError):
        brief.generate_brief(
            meta={},
            params={},
            trades=[_trade()],
            initial_cash=1_000.0,
        )


def test_save_run_brief_validates_when_requested(monkeypatch, tmp_path: Path):
    called: dict[str, bool] = {}

    def fake_validate(*, instance: dict, schema: dict) -> None:
        assert "meta" in instance
        called["seen"] = True

    monkeypatch.setattr(brief.jsonschema, "validate", fake_validate)

    path = brief.save_run_brief(
        tmp_path,
        meta={},
        params={},
        trades=[_trade()],
        initial_cash=500.0,
        validate_schema=True,
    )

    assert path.exists()
    assert called["seen"]


def test_compute_data_quality_penalizes_nans() -> None:
    df = pd.DataFrame({"close": [1.0, float("nan"), 3.0]})
    result = brief.compute_data_quality(df)
    assert result["has_nans"] is True
    assert result["quality_score"] < 1.0

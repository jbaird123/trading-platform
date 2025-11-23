from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from trading_platform.backtester.reporting_pipeline import (
    ReportingPipeline,
    RunArtifactCache,
    ValidationHarness,
)
from trading_platform.portfolio.trade import Trade


def _make_trade(entry_time: datetime) -> Trade:
    exit_time = entry_time + timedelta(minutes=5)
    return Trade(
        symbol="EURUSD",
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=1.0,
        exit_price=1.01,
        side="long",
        size=10_000,
        pnl=100.0,
        exit_reason="strategy_exit",
        stop_loss=None,
        take_profit=None,
        pnl_movement=100.0,
        cost_currency=1.0,
        cost_breakdown={"commission": 0.5, "spread": 0.25, "slippage": 0.25},
        context_at_entry={"strategy_features": {"ema": 1.0}},
        context_at_exit={"strategy_features": {"ema": 1.1}},
    )


def test_reporting_pipeline_generates_brief_and_logs_metrics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify brief generation succeeds and telemetry is captured."""
    pipeline = ReportingPipeline(initial_cash=100_000.0, meta={"strategy": "demo"})
    trades = [
        _make_trade(datetime(2024, 1, 1, tzinfo=timezone.utc)),
        _make_trade(datetime(2024, 1, 2, tzinfo=timezone.utc)),
    ]
    caplog.set_level("INFO")
    brief = pipeline.build_brief(trades=trades)
    assert "overall_performance" in brief
    assert pipeline.telemetry[0].trade_count == 2
    assert any("reporting_metrics" in record.message for record in caplog.records)


def test_trades_dataframe_serializes_context_payloads() -> None:
    """Trades exported for validation should contain context JSON."""
    pipeline = ReportingPipeline(initial_cash=1.0)
    trade = _make_trade(datetime(2024, 1, 1, tzinfo=timezone.utc))
    df = pipeline.trades_dataframe([trade])
    assert "context_at_entry" in df.columns
    payload = pd.Series(df.iloc[0])["context_at_entry"]
    assert '"ema": 1.0' in payload


def test_validation_harness_detects_hash_mismatch() -> None:
    """Hash comparison should flag mismatches for golden exports."""
    df = pd.DataFrame(
        [
            {"symbol": "EURUSD", "exit_price": 1.01},
            {"symbol": "USDJPY", "exit_price": 110.5},
        ]
    )
    harness = ValidationHarness()
    good_hash = harness.hash_dataframe(df)
    modified = df.copy()
    modified.loc[0, "exit_price"] = 1.02
    result = harness.compare(df=modified, expected_hash=good_hash)
    assert not result["match"]
    assert result["actual_hash"] != result["expected_hash"]


def test_run_artifact_cache_roundtrip_returns_copies() -> None:
    """Cache should return deep copies so callers can mutate freely."""
    cache = RunArtifactCache()
    trade = _make_trade(datetime(2024, 1, 1, tzinfo=timezone.utc))
    brief = {"meta": {"strategy": "demo"}}
    cache.save("run-1", trades=[trade], brief=brief)
    cached_trades, cached_brief = cache.load("run-1")
    assert cached_trades[0].context_at_entry is not None
    cached_trades[0].context_at_entry["strategy_features"]["ema"] = 99
    cached_brief["meta"]["strategy"] = "modified"
    reloaded_trades, reloaded_brief = cache.load("run-1")
    assert reloaded_trades[0].context_at_entry is not None
    assert reloaded_trades[0].context_at_entry["strategy_features"]["ema"] == 1.0
    assert reloaded_brief["meta"]["strategy"] == "demo"

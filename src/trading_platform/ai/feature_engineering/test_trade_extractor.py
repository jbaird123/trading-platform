"""Tests for trade data extraction from brief.json files."""

import pandas as pd


def test_extract_trades_from_brief():
    """Test that extract_trades_from_brief extracts and flattens trades."""
    from trading_platform.ai.feature_engineering.trade_extractor import (
        extract_trades_from_brief,
    )

    # Sample brief.json structure with 2 trades
    brief_data = {
        "trades": [
            {
                "entry_time": "2023-01-01T00:00:00",
                "exit_time": "2023-01-01T01:00:00",
                "pnl": 100.0,
                "entry_context": {"RSI_14": 30.5, "EMA_20": 1.1},
                "exit_context": {"RSI_14": 70.2, "EMA_20": 1.15},
            },
            {
                "entry_time": "2023-01-02T00:00:00",
                "exit_time": "2023-01-02T01:00:00",
                "pnl": -50.0,
                "entry_context": {"RSI_14": 65.0, "EMA_20": 1.12},
                "exit_context": {"RSI_14": 35.0, "EMA_20": 1.08},
            },
        ]
    }

    result = extract_trades_from_brief(brief_data)

    # Assertions
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    # Check that nested fields are flattened with '_' separator
    assert "entry_context_RSI_14" in result.columns
    assert "entry_context_EMA_20" in result.columns
    assert "exit_context_RSI_14" in result.columns

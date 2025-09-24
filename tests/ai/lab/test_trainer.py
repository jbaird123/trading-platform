import os
import tempfile
from typing import Any, Dict

from trading_platform.ai.lab import trainer


def mock_brief():
    return {
        "trades": [
            {"id": 1, "entry_context": {"feature1": 1.0, "feature2": 2.0}, "pnl": 10.0},
            {"id": 2, "entry_context": {"feature1": 0.5, "feature2": 1.5}, "pnl": -5.0},
            {"id": 3, "entry_context": {"feature1": 2.0, "feature2": 0.0}, "pnl": 3.0},
        ]
    }


def test_train_profitability_model_and_save():
    brief = mock_brief()
    model, features = trainer.train_profitability_model(brief)
    assert hasattr(model, "predict")
    assert set(features) == {"feature1", "feature2"}
    # Save model
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.joblib")
        trainer.save_model(model, path)
        assert os.path.exists(path)


def test_train_profitability_model_no_trades():
    """Test handling of brief with no trades."""
    import pytest

    brief: Dict[str, Any] = {"trades": []}
    with pytest.raises(ValueError):
        trainer.train_profitability_model(brief)


def test_train_profitability_model_no_entry_context():
    """Test handling of trades missing entry_context key."""
    brief = {
        "trades": [
            {"id": 1, "pnl": 10.0},  # missing entry_context
            {"id": 2, "entry_context": {"feature1": 0.5, "feature2": 1.5}, "pnl": -5.0},
            {"id": 3, "entry_context": {"feature1": 2.0, "feature2": 0.0}, "pnl": 3.0},
        ]
    }
    # Should run without error and train on available data
    model, features = trainer.train_profitability_model(brief)
    assert hasattr(model, "predict")
    assert set(features) == {"feature1", "feature2"}


def test_train_profitability_model_empty_entry_context():
    """Test handling of trades with empty entry_context dictionaries."""
    brief = {
        "trades": [
            {"id": 1, "entry_context": {}, "pnl": 10.0},  # empty entry_context
            {"id": 2, "entry_context": {"feature1": 0.5, "feature2": 1.5}, "pnl": -5.0},
            {"id": 3, "entry_context": {"feature1": 2.0, "feature2": 0.0}, "pnl": 3.0},
        ]
    }
    # Should run without error
    model, features = trainer.train_profitability_model(brief)
    assert hasattr(model, "predict")
    assert set(features) == {"feature1", "feature2"}

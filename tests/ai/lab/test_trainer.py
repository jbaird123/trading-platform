import pytest
import tempfile
import os
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

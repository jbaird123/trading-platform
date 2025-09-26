from unittest.mock import Mock, patch

import numpy as np
from trading_platform.ai.lab import predictor, trainer


def mock_brief():
    return {
        "trades": [
            {"id": 1, "entry_context": {"feature1": 1.0, "feature2": 2.0}, "pnl": 10.0},
            {"id": 2, "entry_context": {"feature1": 0.5, "feature2": 1.5}, "pnl": -5.0},
            {"id": 3, "entry_context": {"feature1": 2.0, "feature2": 0.0}, "pnl": 3.0},
        ]
    }


def test_get_trade_insights():
    brief = mock_brief()
    model, features = trainer.train_profitability_model(brief)
    trade = brief["trades"][0]
    insights = predictor.get_trade_insights(model, trade, features)
    assert "predicted_profitable" in insights
    assert "feature_importances" in insights
    assert isinstance(insights["feature_importances"], dict)


def test_get_trade_insights_missing_context():
    """Test handling of trade missing entry_context key."""
    brief = mock_brief()
    model, features = trainer.train_profitability_model(brief)
    trade = {"id": 1, "pnl": 10.0}  # missing entry_context
    insights = predictor.get_trade_insights(model, trade, features)
    # Should return valid dictionary structure with default/None values
    assert isinstance(insights, dict)
    assert "predicted_profitable" in insights
    assert "feature_importances" in insights


def test_get_trade_insights_feature_mismatch():
    """Test handling of features not present in trade's entry_context."""
    brief = mock_brief()
    model, features = trainer.train_profitability_model(brief)
    trade = {
        "id": 1,
        "entry_context": {"feature1": 1.0},
        "pnl": 10.0,
    }  # missing feature2
    # Use the same features the model was trained on, but trade is missing some features
    insights = predictor.get_trade_insights(model, trade, features)
    # Should handle missing values gracefully (NaN) and return valid insight dictionary
    assert isinstance(insights, dict)
    assert "predicted_profitable" in insights
    assert "feature_importances" in insights
    # feature2 should be NaN in feature importances since it's missing from context
    assert "feature2" in insights["feature_importances"]


# --- Consolidated from tests/ai/test_lab_predictor_coverage_gaps.py ---


def test_get_trade_insights_shap_list_format():
    """SHAP returning a list should select the positive-class contribution."""

    features = ["feature1", "feature2", "feature3"]
    trade = {"entry_context": {"feature1": 1.0, "feature2": 2.0, "feature3": 3.0}}
    mock_model = Mock()
    mock_model.predict.return_value = [1]
    mock_model.predict_proba.return_value = [[0.3, 0.7]]

    with patch("trading_platform.ai.lab.predictor.shap") as mock_shap:
        mock_explainer = Mock()
        mock_explainer.shap_values.return_value = [
            np.array([[0.1, 0.2, 0.3]]),
            np.array([[0.4, 0.5, 0.6]]),
        ]
        mock_shap.TreeExplainer.return_value = mock_explainer

        result = predictor.get_trade_insights(mock_model, trade, features)

    assert result["predicted_profitable"] is True
    assert result["predicted_probability"] == 0.7
    assert result["feature_importances"] == {
        "feature1": 0.4,
        "feature2": 0.5,
        "feature3": 0.6,
    }


def test_get_trade_insights_shap_array_format():
    """Single-array SHAP output should be handled without indexing errors."""

    features = ["feature1", "feature2"]
    trade = {"entry_context": {"feature1": 1.5, "feature2": 2.5}}
    mock_model = Mock()
    mock_model.predict.return_value = [0]
    mock_model.predict_proba.return_value = [[0.8, 0.2]]

    with patch("trading_platform.ai.lab.predictor.shap") as mock_shap:
        mock_explainer = Mock()
        mock_explainer.shap_values.return_value = np.array([[0.7, 0.8]])
        mock_shap.TreeExplainer.return_value = mock_explainer

        result = predictor.get_trade_insights(mock_model, trade, features)

    assert result["predicted_profitable"] is False
    assert result["predicted_probability"] == 0.2
    assert result["feature_importances"] == {"feature1": 0.7, "feature2": 0.8}

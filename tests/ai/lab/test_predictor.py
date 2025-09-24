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

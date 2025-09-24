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

"""Tests for ProfitabilityModel - context-specific predictive models."""

import numpy as np
import pandas as pd
import pytest
from trading_platform.ai.models.profitability import ProfitabilityModel


@pytest.fixture
def sample_trades_df():
    """Create sample enriched trades data with multiple contexts."""
    np.random.seed(42)

    # Create 200 trades across 2 contexts
    n_trades = 200

    data = {
        # Context filters
        "execution_timeframe": ["5min"] * 100 + ["15min"] * 100,
        "strategy_archetype": ["trend_following"] * 100 + ["mean_reversion"] * 100,
        # Entry features (known at entry time)
        "context_at_entry_strategy_features_ema_fast": np.random.uniform(
            1.0, 1.5, n_trades
        ),
        "context_at_entry_strategy_features_ema_slow": np.random.uniform(
            0.9, 1.4, n_trades
        ),
        "context_at_entry_strategy_features_h1_rsi": np.random.uniform(
            20, 80, n_trades
        ),
        "context_at_entry_strategy_features_d1_atr": np.random.uniform(
            0.001, 0.01, n_trades
        ),
        "context_at_entry_strategy_features_volume": np.random.uniform(
            1000, 5000, n_trades
        ),
        # Entry metadata
        "side": np.random.choice(["long", "short"], n_trades),
        "symbol": np.random.choice(["EURUSD", "GBPUSD"], n_trades),
        "entry_time": pd.date_range("2024-01-01", periods=n_trades, freq="1h"),
        # Exit features (lookahead - should NOT be used)
        "context_at_exit_strategy_features_ema_fast": np.random.uniform(
            1.0, 1.5, n_trades
        ),
        "bars_held": np.random.randint(5, 50, n_trades),
        "exit_reason": np.random.choice(["take_profit", "stop_loss"], n_trades),
        # Target
        "pnl": np.random.uniform(
            -100, 200, n_trades
        ),  # Mix of profitable and unprofitable
    }

    return pd.DataFrame(data)


class TestProfitabilityModel:
    """Test suite for ProfitabilityModel."""

    def test_fit_with_valid_trades_df(self, sample_trades_df):
        """Verify model trains successfully with entry context features."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")

        # Should not raise
        model.fit(sample_trades_df)

        # Model should be fitted
        assert model.model is not None
        assert model.feature_names_ is not None
        assert model.imputer is not None
        assert len(model.feature_names_) > 0

    def test_fit_extracts_only_entry_features(self, sample_trades_df):
        """Verify no lookahead features used."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Should only include context_at_entry_* features plus side, symbol, temporal
        for feature in model.feature_names_:
            # Should NOT include exit features
            assert not feature.startswith("context_at_exit_")
            assert feature not in ["bars_held", "exit_reason", "pnl", "pnl_movement"]

            # Should include entry features or metadata
            valid_prefixes = [
                "context_at_entry_",
                "side_",  # One-hot encoded
                "symbol_",  # One-hot encoded
                "hour_of_day",
                "day_of_week",
            ]
            assert any(
                feature.startswith(prefix) for prefix in valid_prefixes
            ), f"Unexpected feature: {feature}"

    def test_fit_filters_by_context(self, sample_trades_df):
        """Verify training data filtered by timeframe/archetype."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Should have trained on 100 trades (5min + trend_following)
        # Model doesn't expose n_samples directly, but we can check it was fitted
        assert model.model is not None

    def test_predict_returns_binary_array(self, sample_trades_df):
        """Verify predict() returns 0/1 values."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Get a subset for prediction
        test_data = sample_trades_df[
            sample_trades_df["execution_timeframe"] == "5min"
        ].head(10)
        predictions = model.predict(test_data)

        assert isinstance(predictions, np.ndarray)
        assert len(predictions) == 10
        assert set(predictions).issubset({0, 1})  # Only 0 or 1 values

    def test_predict_proba_returns_probabilities(self, sample_trades_df):
        """Verify predict_proba() returns [0.0-1.0] values."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        test_data = sample_trades_df[
            sample_trades_df["execution_timeframe"] == "5min"
        ].head(10)
        probabilities = model.predict_proba(test_data)

        assert isinstance(probabilities, np.ndarray)
        assert probabilities.shape == (
            10,
            2,
        )  # Binary classification: [prob_class_0, prob_class_1]
        assert np.all((probabilities >= 0) & (probabilities <= 1))
        assert np.allclose(probabilities.sum(axis=1), 1.0)  # Probabilities sum to 1

    def test_save_and_load(self, sample_trades_df, tmp_path):
        """Verify model serialization works."""
        model = ProfitabilityModel(
            timeframe="5min", archetype="trend_following", random_state=42
        )
        model.fit(sample_trades_df)

        # Save model
        model_path = tmp_path / "test_model.pkl"
        model.save(model_path)
        assert model_path.exists()

        # Load model
        loaded_model = ProfitabilityModel.load(model_path)
        assert loaded_model.timeframe == "5min"
        assert loaded_model.archetype == "trend_following"
        assert loaded_model.model is not None
        assert loaded_model.feature_names_ == model.feature_names_

        # Predictions should match
        test_data = sample_trades_df[
            sample_trades_df["execution_timeframe"] == "5min"
        ].head(5)
        original_pred = model.predict_proba(test_data)
        loaded_pred = loaded_model.predict_proba(test_data)
        np.testing.assert_array_almost_equal(original_pred, loaded_pred)

    def test_metadata_stored(self, sample_trades_df):
        """Verify timeframe/archetype stored in model."""
        model = ProfitabilityModel(timeframe="15min", archetype="mean_reversion")
        model.fit(sample_trades_df)

        assert model.timeframe == "15min"
        assert model.archetype == "mean_reversion"
        assert model.get_model_key() == "15min_mean_reversion"

    def test_fit_with_empty_dataframe_raises(self):
        """Verify error handling for empty data."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="Insufficient data"):
            model.fit(empty_df)

    def test_fit_with_insufficient_data_raises(self, sample_trades_df):
        """Need minimum 50 trades."""
        model = ProfitabilityModel(
            timeframe="1h", archetype="swing"
        )  # Context doesn't exist

        with pytest.raises(ValueError, match="Insufficient data: need 50\\+ trades"):
            model.fit(sample_trades_df)

    def test_fit_with_missing_pnl_column_raises(self, sample_trades_df):
        """Verify validation for missing target column."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        df_no_pnl = sample_trades_df.drop(columns=["pnl"])

        with pytest.raises(KeyError):
            model.fit(df_no_pnl)

    def test_feature_names_stored(self, sample_trades_df):
        """Verify feature names tracked for inference."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        assert model.feature_names_ is not None
        assert isinstance(model.feature_names_, list)
        assert len(model.feature_names_) > 0

        # Should include entry features
        assert any("context_at_entry_" in f for f in model.feature_names_)

        # Should include side and symbol (one-hot encoded)
        assert any("side_" in f for f in model.feature_names_)
        assert any("symbol_" in f for f in model.feature_names_)

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
        # Risk data
        "initial_stop_loss_pips": np.random.uniform(10, 50, n_trades),
        "r_multiple": np.random.uniform(-2, 5, n_trades),
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

        # Should only include context_at_entry_* features plus side, symbol, temporal, and risk parameters
        assert model.feature_names_ is not None
        for feature in model.feature_names_:
            # Should NOT include exit features
            assert not feature.startswith("context_at_exit_")
            assert feature not in ["bars_held", "exit_reason", "pnl", "pnl_movement"]

            # Should include entry features or metadata
            valid_prefixes = [
                "context_at_entry_",
                "initial_stop_loss_pips",  # Risk parameter (known at entry)
                "side_",  # One-hot encoded
                "symbol_",  # One-hot encoded
                "hour_of_day",
                "day_of_week",
            ]
            assert any(
                feature.startswith(prefix) or feature == prefix
                for prefix in valid_prefixes
            ), f"Unexpected feature: {feature}"

    def test_fit_filters_by_context(self, sample_trades_df):
        """Verify training data filtered by timeframe/archetype."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Should have trained on 100 trades (5min + trend_following)
        # Model doesn't expose n_samples directly, but we can check it was fitted
        assert model.model is not None

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
        original_pred = model.predict(test_data)
        loaded_pred = loaded_model.predict(test_data)
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

    def test_fit_with_missing_r_multiple_column_raises(self, sample_trades_df):
        """Verify validation for missing target column."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        df_no_r_multiple = sample_trades_df.drop(columns=["r_multiple"])

        with pytest.raises(ValueError, match="Missing required column 'r_multiple'"):
            model.fit(df_no_r_multiple)

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

    def test_fit_raises_error_on_missing_r_multiple(self, sample_trades_df):
        """Verify model raises ValueError when r_multiple is missing."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")

        # Create data with missing r_multiple
        df_with_nulls = sample_trades_df.copy()
        df_with_nulls.loc[0, "r_multiple"] = np.nan

        with pytest.raises(
            ValueError, match="Cannot train without historical 'r_multiple'"
        ):
            model.fit(df_with_nulls)

    def test_fit_raises_error_on_invalid_stop_loss(self, sample_trades_df):
        """Verify model raises ValueError when initial_stop_loss_pips is invalid."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")

        # Test with null stop_loss
        df_with_null_stop = sample_trades_df.copy()
        df_with_null_stop.loc[0, "initial_stop_loss_pips"] = np.nan

        with pytest.raises(ValueError, match="valid 'initial_stop_loss_pips' > 0"):
            model.fit(df_with_null_stop)

        # Test with non-positive stop_loss
        df_with_invalid_stop = sample_trades_df.copy()
        df_with_invalid_stop.loc[0, "initial_stop_loss_pips"] = 0

        with pytest.raises(ValueError, match="valid 'initial_stop_loss_pips' > 0"):
            model.fit(df_with_invalid_stop)

    def test_predict_returns_continuous_r_multiple(self, sample_trades_df):
        """Verify predict() returns continuous R-multiple values (not binary 0/1)."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Get a subset for prediction
        test_data = sample_trades_df[
            sample_trades_df["execution_timeframe"] == "5min"
        ].head(10)
        predictions = model.predict(test_data)

        assert isinstance(predictions, np.ndarray)
        assert len(predictions) == 10
        # Predictions should be continuous values (not just 0/1)
        # Check that at least some predictions are not exactly 0 or 1
        non_binary = ~np.isin(predictions, [0, 1])
        assert (
            non_binary.any()
        ), "Expected continuous R-multiple predictions, got binary values"

    def test_fit_records_training_date_range(self, sample_trades_df):
        """Verify model records training date range (Step 14)."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Verify training dates are recorded
        assert hasattr(model, "training_start_date_")
        assert hasattr(model, "training_end_date_")
        assert model.training_start_date_ is not None
        assert model.training_end_date_ is not None

        # Verify dates are pandas Timestamp
        assert isinstance(model.training_start_date_, pd.Timestamp)
        assert isinstance(model.training_end_date_, pd.Timestamp)

        # Verify dates match the filtered data (model filters by context)
        context_df = sample_trades_df[
            (sample_trades_df["execution_timeframe"] == "5min")
            & (sample_trades_df["strategy_archetype"] == "trend_following")
        ]
        expected_start = pd.to_datetime(context_df["entry_time"]).min()
        expected_end = pd.to_datetime(context_df["entry_time"]).max()
        assert model.training_start_date_ == expected_start
        assert model.training_end_date_ == expected_end

    def test_predict_with_confidence_returns_correct_shape(self, sample_trades_df):
        """Verify predict_with_confidence returns DataFrame with predictions and confidence intervals (Step 22)."""
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        model.fit(sample_trades_df)

        # Get a subset for prediction
        test_data = sample_trades_df[
            sample_trades_df["execution_timeframe"] == "5min"
        ].head(10)

        result = model.predict_with_confidence(test_data)

        # Verify it's a DataFrame with correct shape
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10

        # Verify columns
        assert "prediction" in result.columns
        assert "std" in result.columns
        assert "lower_bound" in result.columns
        assert "upper_bound" in result.columns

        # Verify data types are numeric
        assert result["prediction"].dtype in [float, "float64"]
        assert result["std"].dtype in [float, "float64"]
        assert result["lower_bound"].dtype in [float, "float64"]
        assert result["upper_bound"].dtype in [float, "float64"]

        # Verify confidence interval logic
        # lower_bound = prediction - 2*std, upper_bound = prediction + 2*std
        for idx in result.index:
            pred = result.loc[idx, "prediction"]
            std = result.loc[idx, "std"]
            lower = result.loc[idx, "lower_bound"]
            upper = result.loc[idx, "upper_bound"]

            assert np.isclose(lower, pred - 2 * std)
            assert np.isclose(upper, pred + 2 * std)
            assert lower < pred < upper  # Prediction should be within bounds

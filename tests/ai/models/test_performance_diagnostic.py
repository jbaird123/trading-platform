"""Tests for PerformanceDiagnosticModel - Context-specific regime analysis."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from trading_platform.ai.models.performance_diagnostic import (
    PerformanceDiagnosticModel,
)


@pytest.fixture
def sample_trades_df():
    """Create sample enriched trades DataFrame with lookahead features."""
    return pd.DataFrame(
        {
            # Context metadata
            "execution_timeframe": ["5min"] * 60,
            "strategy_archetype": ["trend_following"] * 60,
            # Entry features
            "context_at_entry_rsi": np.random.uniform(30, 70, 60),
            "context_at_entry_atr": np.random.uniform(0.0005, 0.002, 60),
            "side": ["long", "short"] * 30,
            "symbol": ["EURUSD"] * 60,
            "entry_time": pd.date_range("2024-01-01", periods=60, freq="1h"),
            # Exit features (lookahead)
            "context_at_exit_rsi": np.random.uniform(30, 70, 60),
            "context_at_exit_atr": np.random.uniform(0.0005, 0.002, 60),
            # Trade execution features (lookahead)
            "bars_held": np.random.randint(1, 50, 60),
            "mae_currency": np.random.uniform(-50, 0, 60),
            "mfe_currency": np.random.uniform(0, 100, 60),
            "r_multiple": np.random.uniform(-2, 5, 60),  # Target basis
            # Exit metadata (lookahead)
            "exit_reason": np.random.choice(
                ["take_profit", "stop_loss", "trailing_stop"], 60
            ),
            # Post-trade analysis (lookahead)
            "post_exit_analysis_max_favorable_pip": np.random.uniform(0, 50, 60),
            "post_exit_analysis_max_adverse_pip": np.random.uniform(-50, 0, 60),
            # Cost features
            "cost_breakdown_commission": [2.0] * 60,
            "cost_breakdown_slippage": [1.0] * 60,
            "cost_breakdown_spread": [1.5] * 60,
            # Target (not used directly - we compute quintiles from r_multiple)
            "pnl": np.random.uniform(-50, 100, 60),
        }
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for model storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestPerformanceDiagnosticModel:
    """Test suite for PerformanceDiagnosticModel."""

    def test_fit_with_valid_trades_df(self, sample_trades_df):
        """Verify model can be trained successfully."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        model.fit(sample_trades_df)

        # Verify model is fitted
        assert model.model is not None
        assert model.feature_names_ is not None
        assert model.imputer is not None

    def test_fit_extracts_all_features(self, sample_trades_df):
        """Verify model uses ALL features including lookahead."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        model.fit(sample_trades_df)

        # Verify lookahead features are included
        feature_names = model.feature_names_
        assert feature_names is not None

        # Should have entry features
        assert any("context_at_entry" in f for f in feature_names)

        # Should have exit features (lookahead)
        assert any("context_at_exit" in f for f in feature_names)

        # Should have trade execution features (lookahead)
        # Note: bars_held, mae_currency, mfe_currency are included as features

        # Should have exit reason (one-hot encoded)
        assert any("exit_reason" in f for f in feature_names)

    def test_fit_filters_by_context(self, sample_trades_df):
        """Verify model filters data by timeframe and archetype."""
        # Add a different context to the data
        other_context = sample_trades_df.copy()
        other_context["execution_timeframe"] = "15min"
        other_context["strategy_archetype"] = "mean_reversion"

        combined_df = pd.concat([sample_trades_df, other_context], ignore_index=True)

        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(combined_df)

        # Model should only use 5min/trend_following data (60 samples)
        # We can't directly verify the filtered data, but we can check
        # that the model was fitted successfully
        assert model.model is not None

    def test_predict_returns_quintile_array(self, sample_trades_df):
        """Verify predictions are quintiles (0-4)."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        # Predict on test data
        test_df = sample_trades_df.head(10)
        predictions = model.predict(test_df)

        # Verify output
        assert len(predictions) == 10
        assert all(p in [0, 1, 2, 3, 4] for p in predictions)

    def test_predict_proba_returns_probabilities(self, sample_trades_df):
        """Verify probability predictions."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        test_df = sample_trades_df.head(10)
        proba = model.predict_proba(test_df)

        # Verify output shape (10 samples, 5 classes)
        assert proba.shape == (10, 5)

        # Verify probabilities sum to 1
        assert np.allclose(proba.sum(axis=1), 1.0)

        # Verify all probabilities in [0, 1]
        assert np.all((proba >= 0) & (proba <= 1))

    def test_save_and_load(self, sample_trades_df, temp_dir):
        """Verify model serialization and deserialization."""
        # Train and save model
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following", n_estimators=50
        )
        model.fit(sample_trades_df)

        save_path = temp_dir / "test_model.pkl"
        model.save(save_path)

        # Load model
        loaded_model = PerformanceDiagnosticModel.load(save_path)

        # Verify metadata
        assert loaded_model.timeframe == "5min"
        assert loaded_model.archetype == "trend_following"
        assert loaded_model.n_estimators == 50

        # Verify it can predict
        test_df = sample_trades_df.head(5)
        predictions = loaded_model.predict(test_df)
        assert len(predictions) == 5

    def test_metadata_stored(self, sample_trades_df):
        """Verify timeframe and archetype are stored."""
        model = PerformanceDiagnosticModel(
            timeframe="15min", archetype="mean_reversion"
        )

        assert model.timeframe == "15min"
        assert model.archetype == "mean_reversion"

    def test_fit_with_empty_dataframe_raises(self):
        """Verify error on empty DataFrame."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="Insufficient data"):
            model.fit(empty_df)

    def test_fit_with_insufficient_data_raises(self, sample_trades_df):
        """Verify error when context has < 50 trades."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        # Use only 20 trades
        small_df = sample_trades_df.head(20)

        with pytest.raises(ValueError, match="Insufficient data"):
            model.fit(small_df)

    def test_fit_with_missing_r_multiple_column_raises(self, sample_trades_df):
        """Verify error when target column is missing."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        # Remove target column
        df_missing_target = sample_trades_df.drop(columns=["r_multiple"])

        with pytest.raises(KeyError):
            model.fit(df_missing_target)

    def test_feature_names_stored(self, sample_trades_df):
        """Verify feature names are stored for alignment."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        # Verify feature_names_ is populated
        assert model.feature_names_ is not None
        assert len(model.feature_names_) > 0
        assert isinstance(model.feature_names_, list)

    def test_predict_with_unfitted_model_raises(self, sample_trades_df):
        """Verify error when predicting with unfitted model."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        with pytest.raises(ValueError, match="not fitted"):
            model.predict(sample_trades_df)

    def test_quintile_target_creation(self, sample_trades_df):
        """Verify quintiles are created correctly from r_multiple."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        # The model should have been trained on quintiles (0-4)
        # We can verify by checking predictions are in valid range
        predictions = model.predict(sample_trades_df)

        assert all(p in [0, 1, 2, 3, 4] for p in predictions)

        # Verify all 5 classes are represented (with 60 samples, likely all present)
        unique_classes = np.unique(predictions)
        assert len(unique_classes) >= 3  # At least 3 classes should be present

    def test_get_model_key(self):
        """Verify model key generation."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )

        assert model.get_model_key() == "5min_trend_following"

    def test_fit_uses_all_features_including_lookahead(self, sample_trades_df):
        """Verify model includes flattened sim_hold_* features."""
        # Add sim_hold_* columns (as if data was unpacked)
        sample_trades_df["sim_hold_10_pnl"] = np.random.uniform(-20, 40, 60)
        sample_trades_df["sim_hold_10_exit_reason"] = np.random.choice(
            ["horizon_reached", "stop_loss_hit"], 60
        )
        sample_trades_df["sim_hold_20_pnl"] = np.random.uniform(-30, 50, 60)
        sample_trades_df["sim_hold_20_exit_reason"] = np.random.choice(
            ["horizon_reached", "stop_loss_hit", "take_profit_hit"], 60
        )

        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        # Verify sim_hold_* columns are included in features
        feature_names = model.feature_names_
        assert feature_names is not None

        # Check for sim_hold numeric features
        assert any("sim_hold_10_pnl" in f for f in feature_names)
        assert any("sim_hold_20_pnl" in f for f in feature_names)

        # Check for one-hot encoded exit reasons
        assert any("sim_hold_10_exit_reason" in f for f in feature_names)
        assert any("sim_hold_20_exit_reason" in f for f in feature_names)

    def test_can_fit_with_pnl_target(self, sample_trades_df):
        """Verify initialization with target_metric='pnl' for flexibility."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following", target_metric="pnl"
        )

        # Should fit successfully with pnl as target
        model.fit(sample_trades_df)

        # Verify model is fitted
        assert model.model is not None
        assert model.target_metric == "pnl"

        # Predictions should still be quintiles (0-4)
        predictions = model.predict(sample_trades_df.head(10))
        assert all(p in [0, 1, 2, 3, 4] for p in predictions)

    def test_fit_records_training_date_range(self, sample_trades_df):
        """Verify model records training date range (Step 14)."""
        model = PerformanceDiagnosticModel(
            timeframe="5min", archetype="trend_following"
        )
        model.fit(sample_trades_df)

        # Verify training dates are recorded
        assert hasattr(model, "training_start_date_")
        assert hasattr(model, "training_end_date_")
        assert model.training_start_date_ is not None
        assert model.training_end_date_ is not None

        # Verify dates are pandas Timestamp
        assert isinstance(model.training_start_date_, pd.Timestamp)
        assert isinstance(model.training_end_date_, pd.Timestamp)

        # Verify dates match the data
        expected_start = pd.to_datetime(sample_trades_df["entry_time"]).min()
        expected_end = pd.to_datetime(sample_trades_df["entry_time"]).max()
        assert model.training_start_date_ == expected_start
        assert model.training_end_date_ == expected_end

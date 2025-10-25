"""Tests for ModelRegistry - Central manager for profitability and diagnostic models."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from trading_platform.ai.models.profitability import ProfitabilityModel
from trading_platform.ai.models.registry import ModelRegistry


@pytest.fixture
def sample_trades_df():
    """Create sample enriched trades DataFrame for testing."""
    # Create 50 trades per context (4 contexts = 200 total trades)
    # Contexts: 5min/trend, 5min/mean_reversion, 15min/trend, 15min/mean_reversion
    return pd.DataFrame(
        {
            # Context metadata
            "execution_timeframe": ["5min"] * 100 + ["15min"] * 100,
            "strategy_archetype": ["trend_following"] * 50
            + ["mean_reversion"] * 50
            + ["trend_following"] * 50
            + ["mean_reversion"] * 50,
            # Entry features
            "context_at_entry_rsi": [50.0] * 200,
            "context_at_entry_atr": [0.001] * 200,
            "side": ["long", "short"] * 100,
            "symbol": ["EUR_USD"] * 200,
            "entry_time": pd.date_range("2024-01-01", periods=200, freq="1h"),
            # Target
            "pnl": [10.0, -5.0] * 100,  # Alternating profitable/unprofitable
        }
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for model storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestModelRegistry:
    """Test suite for ModelRegistry."""

    def test_register_model(self, temp_dir):
        """Verify model registration."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Create and register a model
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        registry.register_model("profitability", "5min_trend_following", model)

        # Verify registration
        assert "5min_trend_following" in registry.list_models("profitability")

    def test_register_duplicate_key_raises(self, temp_dir):
        """Verify duplicate key detection."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Register first model
        model1 = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        registry.register_model("profitability", "5min_trend_following", model1)

        # Attempt to register duplicate
        model2 = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        with pytest.raises(ValueError, match="already registered"):
            registry.register_model("profitability", "5min_trend_following", model2)

    def test_get_model_exists(self, temp_dir):
        """Verify model retrieval."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Register model
        model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
        registry.register_model("profitability", "5min_trend_following", model)

        # Retrieve model
        retrieved = registry.get_model("profitability", "5min_trend_following")
        assert retrieved is model
        assert retrieved.timeframe == "5min"
        assert retrieved.archetype == "trend_following"

    def test_get_model_not_exists_returns_none(self, temp_dir):
        """Verify missing model handling."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Attempt to get non-existent model
        result = registry.get_model("profitability", "nonexistent")
        assert result is None

    def test_list_models(self, temp_dir):
        """Verify listing all registered models."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Register multiple models
        registry.register_model(
            "profitability",
            "5min_trend_following",
            ProfitabilityModel("5min", "trend_following"),
        )
        registry.register_model(
            "profitability",
            "15min_mean_reversion",
            ProfitabilityModel("15min", "mean_reversion"),
        )

        # Verify listing
        models = registry.list_models("profitability")
        assert len(models) == 2
        assert "5min_trend_following" in models
        assert "15min_mean_reversion" in models

    def test_list_models_empty_family(self, temp_dir):
        """Verify listing models for empty family."""
        registry = ModelRegistry(model_dir=temp_dir)

        # List models for family with no models
        models = registry.list_models("profitability")
        assert models == []

    def test_save_and_load_registry(self, temp_dir, sample_trades_df):
        """Verify registry serialization and deserialization."""
        # Create and populate registry
        registry = ModelRegistry(model_dir=temp_dir)

        model = ProfitabilityModel("5min", "trend_following")
        model.fit(sample_trades_df)  # Fit so it's saveable
        registry.register_model("profitability", "5min_trend_following", model)

        # Save registry
        registry.save()

        # Load into new registry
        new_registry = ModelRegistry(model_dir=temp_dir)
        new_registry.load()

        # Verify loaded model
        loaded_model = new_registry.get_model("profitability", "5min_trend_following")
        assert loaded_model is not None
        assert loaded_model.timeframe == "5min"
        assert loaded_model.archetype == "trend_following"
        assert loaded_model.model is not None  # Verify it's fitted

    def test_get_or_create_model(self, temp_dir):
        """Verify lazy model instantiation."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Get model that doesn't exist (should create)
        model = registry.get_or_create_profitability_model(
            timeframe="5min", archetype="trend_following"
        )

        assert model is not None
        assert model.timeframe == "5min"
        assert model.archetype == "trend_following"

        # Verify it was registered
        assert "5min_trend_following" in registry.list_models("profitability")

        # Get same model again (should return existing)
        model2 = registry.get_or_create_profitability_model(
            timeframe="5min", archetype="trend_following"
        )
        assert model2 is model  # Same instance

    def test_train_all_profitability_models(self, temp_dir, sample_trades_df):
        """Verify batch training of profitability models."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Train all models from enriched data
        trained_models = registry.train_all_profitability_models(sample_trades_df)

        # Verify all contexts were trained
        # Data has: 5min/trend, 5min/mean_reversion, 15min/trend, 15min/mean_reversion
        assert len(trained_models) == 4
        assert "5min_trend_following" in trained_models
        assert "5min_mean_reversion" in trained_models
        assert "15min_trend_following" in trained_models
        assert "15min_mean_reversion" in trained_models

        # Verify models are fitted
        for key, model in trained_models.items():
            assert model.model is not None
            assert model.feature_names_ is not None

    def test_train_profitability_models_insufficient_data_skips(self, temp_dir):
        """Verify contexts with insufficient data are skipped."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Create data with only 10 trades per context (need 50)
        small_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 10,
                "strategy_archetype": ["trend_following"] * 10,
                "context_at_entry_rsi": [50.0] * 10,
                "side": ["long"] * 10,
                "symbol": ["EUR_USD"] * 10,
                "entry_time": pd.date_range("2024-01-01", periods=10, freq="1h"),
                "pnl": [10.0] * 10,
            }
        )

        # Train models (should skip due to insufficient data and emit warning)
        trained_models = registry.train_all_profitability_models(small_df)

        # Verify no models were trained
        assert len(trained_models) == 0

    def test_predict_with_profitability_model(self, temp_dir, sample_trades_df):
        """Verify prediction routing to correct model."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Train models
        registry.train_all_profitability_models(sample_trades_df)

        # Create test data for 5min/trend_following context
        test_df = sample_trades_df[
            (sample_trades_df["execution_timeframe"] == "5min")
            & (sample_trades_df["strategy_archetype"] == "trend_following")
        ].head(5)

        # Predict
        predictions = registry.predict_profitability(
            X=test_df, timeframe="5min", archetype="trend_following"
        )

        # Verify predictions
        assert len(predictions) == 5
        assert all(p in [0, 1] for p in predictions)

    def test_predict_with_missing_model_raises(self, temp_dir, sample_trades_df):
        """Verify error when predicting with non-existent model."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Attempt prediction without training
        with pytest.raises(ValueError, match="not found"):
            registry.predict_profitability(
                X=sample_trades_df.head(5),
                timeframe="5min",
                archetype="trend_following",
            )

    def test_get_model_path(self, temp_dir):
        """Verify model path generation."""
        registry = ModelRegistry(model_dir=temp_dir)

        path = registry.get_model_path("profitability", "5min_trend_following")

        expected = temp_dir / "profitability" / "5min_trend_following.pkl"
        assert path == expected

    def test_separate_profitability_and_diagnostic_families(self, temp_dir):
        """Verify profitability and diagnostic models are separate."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Register models in both families
        prof_model = ProfitabilityModel("5min", "trend_following")
        registry.register_model("profitability", "5min_trend_following", prof_model)

        # For now, we'll just register another profitability model
        # (PerformanceDiagnosticModel doesn't exist yet)
        diag_model = ProfitabilityModel("5min", "trend_following")  # Placeholder
        registry.register_model("diagnostic", "5min_trend_following", diag_model)

        # Verify separate listings
        prof_models = registry.list_models("profitability")
        diag_models = registry.list_models("diagnostic")

        assert len(prof_models) == 1
        assert len(diag_models) == 1

        # Verify they're different instances
        assert registry.get_model("profitability", "5min_trend_following") is prof_model
        assert registry.get_model("diagnostic", "5min_trend_following") is diag_model

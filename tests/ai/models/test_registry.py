"""Tests for ModelRegistry - Central manager for profitability and diagnostic models."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from trading_platform.ai.models.performance_diagnostic import PerformanceDiagnosticModel
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
            # Target and risk data
            "pnl": [10.0, -5.0] * 100,  # Alternating profitable/unprofitable
            "initial_stop_loss_pips": [20.0] * 200,
            "r_multiple": [0.5, -0.25] * 100,
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

    def test_train_profitability_models_insufficient_data_raises(self, temp_dir):
        """Verify training fails with insufficient data."""
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
                "r_multiple": [0.5] * 10,
                "initial_stop_loss_pips": [20.0] * 10,
            }
        )

        # Verify training raises ValueError due to insufficient data
        with pytest.raises(
            ValueError,
            match="Insufficient data: need 50\\+ trades for 5min_trend_following",
        ):
            registry.train_all_profitability_models(small_df)

    def test_predict_with_profitability_model(self, temp_dir, sample_trades_df):
        """Verify prediction routing to correct model."""
        import numpy as np

        registry = ModelRegistry(model_dir=temp_dir)

        # Train models
        registry.train_all_profitability_models(sample_trades_df)

        # Create NEW test data that doesn't overlap with training period
        # Training data ends at some point, so we create data after that
        test_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 5,
                "strategy_archetype": ["trend_following"] * 5,
                "context_at_entry_rsi": np.random.uniform(30, 70, 5),
                "context_at_entry_atr": np.random.uniform(0.0005, 0.002, 5),
                "side": ["long", "short", "long", "short", "long"],
                "symbol": ["EUR_USD"] * 5,
                "entry_time": pd.date_range(
                    "2025-01-01", periods=5, freq="1h"
                ),  # Future data
                "initial_stop_loss_pips": np.random.uniform(10, 50, 5),
            }
        )

        # Predict
        predictions = registry.predict_profitability(
            X=test_df, timeframe="5min", archetype="trend_following"
        )

        # Verify predictions are continuous R-multiple values
        assert len(predictions) == 5
        assert isinstance(predictions, pd.Series)
        # Predictions should be floats (not just 0/1)
        assert predictions.dtype in [float, "float64"]

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

    def test_train_all_diagnostic_from_enriched(
        self, temp_dir, sample_trades_df, mocker
    ):
        """Verify that enriched data is unpacked before training diagnostic models."""
        registry = ModelRegistry(model_dir=temp_dir)

        # Add the nested post_exit_analysis_simulated_holds column to sample data
        sample_trades_df["post_exit_analysis_simulated_holds"] = [
            [
                {"hold_bars": 10, "pnl": 50.0, "exit_reason": "horizon_reached"},
                {"hold_bars": 20, "pnl": -25.0, "exit_reason": "stop_loss_hit"},
            ]
        ] * len(sample_trades_df)

        # Add r_multiple column (needed by PerformanceDiagnosticModel)
        # Need diverse values for quintile classification
        import numpy as np

        np.random.seed(42)
        sample_trades_df["r_multiple"] = np.random.uniform(-2.0, 3.0, 200)

        # Spy on PerformanceDiagnosticModel.fit to verify the unpacked data
        fit_spy = mocker.spy(PerformanceDiagnosticModel, "fit")

        # Train diagnostic models
        trained_models = registry.train_all_diagnostic_from_enriched(sample_trades_df)

        # Verify that fit was called
        assert fit_spy.call_count > 0

        # Get the DataFrame that was passed to the first fit call
        first_call_args = fit_spy.call_args_list[0]
        df_passed_to_fit = first_call_args[0][1]  # self, df

        # Verify the DataFrame has the unpacked columns and not the original
        assert "sim_hold_10_pnl" in df_passed_to_fit.columns
        assert "sim_hold_10_exit_reason" in df_passed_to_fit.columns
        assert "sim_hold_20_pnl" in df_passed_to_fit.columns
        assert "sim_hold_20_exit_reason" in df_passed_to_fit.columns
        assert "post_exit_analysis_simulated_holds" not in df_passed_to_fit.columns

        # Verify all contexts were trained
        assert len(trained_models) == 4

    def test_train_all_diagnostic_models_segregates_by_risk(self, temp_dir):
        """Verify diagnostic models are segregated by data availability (Step 10)."""
        import numpy as np

        registry = ModelRegistry(model_dir=temp_dir)

        # Create mixed data: some with r_multiple, some without
        # 100 trades with r_multiple (can train rmultiple model)
        # 50 trades with pnl but no r_multiple (can train pnl_no_risk model)
        # Total 150 for 5min_trend_following context
        df_with_risk = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 100,
                "strategy_archetype": ["trend_following"] * 100,
                "context_at_entry_rsi": np.random.uniform(30, 70, 100),
                "side": ["long", "short"] * 50,
                "symbol": ["EUR_USD"] * 100,
                "entry_time": pd.date_range("2024-01-01", periods=100, freq="1h"),
                "pnl": np.random.uniform(-50, 100, 100),
                "r_multiple": np.random.uniform(-2, 5, 100),  # Has risk data
                "initial_stop_loss_pips": np.random.uniform(10, 50, 100),
            }
        )

        df_no_risk = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 50,
                "strategy_archetype": ["trend_following"] * 50,
                "context_at_entry_rsi": np.random.uniform(30, 70, 50),
                "side": ["long", "short"] * 25,
                "symbol": ["EUR_USD"] * 50,
                "entry_time": pd.date_range("2024-05-01", periods=50, freq="1h"),
                "pnl": np.random.uniform(-50, 100, 50),
                "r_multiple": np.full(50, np.nan),  # No risk data (explicit float NaN)
                "initial_stop_loss_pips": np.full(50, np.nan),
            }
        )

        combined_df = pd.concat([df_with_risk, df_no_risk], ignore_index=True)

        # Add required lookahead features for diagnostic model
        combined_df["context_at_exit_rsi"] = np.random.uniform(30, 70, 150)
        combined_df["bars_held"] = np.random.randint(1, 50, 150)
        combined_df["mae_currency"] = np.random.uniform(-50, 0, 150)
        combined_df["mfe_currency"] = np.random.uniform(0, 100, 150)
        combined_df["exit_reason"] = np.random.choice(["take_profit", "stop_loss"], 150)

        # Train diagnostic models - should create segregated models
        trained_models = registry.train_all_diagnostic_models(combined_df)

        # Verify segregated models were created
        model_keys = list(trained_models.keys())

        # Should have models with different suffixes
        assert any(
            "_rmultiple" in key for key in model_keys
        ), "Expected _rmultiple model"
        assert any(
            "_pnl_no_risk" in key for key in model_keys
        ), "Expected _pnl_no_risk model"

        # Verify models have correct target_metric
        for key, model in trained_models.items():
            if "_rmultiple" in key:
                assert model.target_metric == "r_multiple"
            elif "_pnl_no_risk" in key:
                assert model.target_metric == "pnl"

    def test_analyze_performance_regime_validates_data_type(self, temp_dir):
        """Verify analyze_performance_regime raises error for mismatched data (Step 12)."""
        import numpy as np

        registry = ModelRegistry(model_dir=temp_dir)

        # Train a model on data WITH risk
        df_with_risk = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 100,
                "strategy_archetype": ["trend_following"] * 100,
                "context_at_entry_rsi": np.random.uniform(30, 70, 100),
                "side": ["long", "short"] * 50,
                "symbol": ["EUR_USD"] * 100,
                "entry_time": pd.date_range("2024-01-01", periods=100, freq="1h"),
                "pnl": np.random.uniform(-50, 100, 100),
                "r_multiple": np.random.uniform(-2, 5, 100),
                "initial_stop_loss_pips": np.random.uniform(10, 50, 100),
                "context_at_exit_rsi": np.random.uniform(30, 70, 100),
                "bars_held": np.random.randint(1, 50, 100),
                "mae_currency": np.random.uniform(-50, 0, 100),
                "mfe_currency": np.random.uniform(0, 100, 100),
                "exit_reason": np.random.choice(["take_profit", "stop_loss"], 100),
            }
        )

        trained_models = registry.train_all_diagnostic_models(df_with_risk)

        # Try to use the _no_risk model on data that HAS r_multiple
        # This should raise a ValueError
        test_data_with_risk = df_with_risk.head(10)

        # Get the _no_risk model key (if it exists)
        no_risk_keys = [k for k in trained_models.keys() if "_no_risk" in k]

        if no_risk_keys:
            with pytest.raises(ValueError, match="data type mismatch"):
                registry.analyze_performance_regime(
                    X=test_data_with_risk,
                    timeframe="5min",
                    archetype="trend_following",
                    model_suffix="_pnl_no_risk",
                )

    def test_predict_profitability_raises_lookahead_error(self, temp_dir):
        """Verify predict_profitability detects and prevents lookahead bias (Step 18)."""
        import numpy as np

        registry = ModelRegistry(model_dir=temp_dir)

        # Train a model on specific date range
        training_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 100,
                "strategy_archetype": ["trend_following"] * 100,
                "context_at_entry_rsi": np.random.uniform(30, 70, 100),
                "side": ["long", "short"] * 50,
                "symbol": ["EUR_USD"] * 100,
                "entry_time": pd.date_range("2024-01-01", periods=100, freq="1h"),
                "pnl": np.random.uniform(-50, 100, 100),
                "r_multiple": np.random.uniform(-2, 5, 100),
                "initial_stop_loss_pips": np.random.uniform(10, 50, 100),
            }
        )

        trained_models = registry.train_all_profitability_models(training_df)
        assert len(trained_models) > 0

        # Try to predict on data that overlaps with training period
        # Training period: 2024-01-01 to 2024-01-05 03:00:00 (100 hours)
        overlapping_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 5,
                "strategy_archetype": ["trend_following"] * 5,
                "context_at_entry_rsi": np.random.uniform(30, 70, 5),
                "side": ["long"] * 5,
                "symbol": ["EUR_USD"] * 5,
                "entry_time": pd.date_range(
                    "2024-01-03", periods=5, freq="1h"
                ),  # Overlaps!
                "initial_stop_loss_pips": np.random.uniform(10, 50, 5),
            }
        )

        # Should raise ValueError due to lookahead bias
        with pytest.raises(ValueError, match="Lookahead bias detected"):
            registry.predict_profitability(
                X=overlapping_df, timeframe="5min", archetype="trend_following"
            )

    def test_analyze_performance_regime_raises_lookahead_error(self, temp_dir):
        """Verify analyze_performance_regime detects lookahead bias (Step 19)."""
        import numpy as np

        registry = ModelRegistry(model_dir=temp_dir)

        # Train a diagnostic model
        training_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 100,
                "strategy_archetype": ["trend_following"] * 100,
                "context_at_entry_rsi": np.random.uniform(30, 70, 100),
                "side": ["long", "short"] * 50,
                "symbol": ["EUR_USD"] * 100,
                "entry_time": pd.date_range("2024-01-01", periods=100, freq="1h"),
                "pnl": np.random.uniform(-50, 100, 100),
                "r_multiple": np.random.uniform(-2, 5, 100),
                "initial_stop_loss_pips": np.random.uniform(10, 50, 100),
                "context_at_exit_rsi": np.random.uniform(30, 70, 100),
                "bars_held": np.random.randint(1, 50, 100),
                "mae_currency": np.random.uniform(-50, 0, 100),
                "mfe_currency": np.random.uniform(0, 100, 100),
                "exit_reason": np.random.choice(["take_profit", "stop_loss"], 100),
            }
        )

        trained_models = registry.train_all_diagnostic_models(training_df)
        assert len(trained_models) > 0

        # Try to predict on overlapping data
        overlapping_df = pd.DataFrame(
            {
                "execution_timeframe": ["5min"] * 5,
                "strategy_archetype": ["trend_following"] * 5,
                "context_at_entry_rsi": np.random.uniform(30, 70, 5),
                "side": ["long"] * 5,
                "symbol": ["EUR_USD"] * 5,
                "entry_time": pd.date_range(
                    "2024-01-02", periods=5, freq="1h"
                ),  # Overlaps!
                "r_multiple": np.random.uniform(-2, 5, 5),
                "context_at_exit_rsi": np.random.uniform(30, 70, 5),
                "bars_held": np.random.randint(1, 50, 5),
            }
        )

        # Should raise ValueError due to lookahead bias
        with pytest.raises(ValueError, match="Lookahead bias detected"):
            registry.analyze_performance_regime(
                X=overlapping_df, timeframe="5min", archetype="trend_following"
            )

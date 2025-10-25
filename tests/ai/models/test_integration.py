"""Integration test for ML models with real enriched data.

This test verifies the end-to-end workflow:
1. Load real enriched trade data
2. Train profitability and diagnostic models
3. Save models to disk
4. Load models from disk
5. Make predictions
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from trading_platform.ai.models import (
    ModelRegistry,
    PerformanceDiagnosticModel,
    ProfitabilityModel,
)


@pytest.fixture
def enriched_data_path():
    """Get path to real enriched data if it exists."""
    # Try multiple possible locations
    possible_paths = [
        Path("data/enriched/trend_following_15m_v1/rich_trades.parquet"),
        Path("data/enriched/test_campaign/rich_trades.parquet"),
    ]

    for path in possible_paths:
        if path.exists():
            return path

    pytest.skip("No enriched data available for integration test")


def test_full_workflow_with_real_data(enriched_data_path):
    """Test complete workflow with real enriched data."""
    # Load real data
    df = pd.read_parquet(enriched_data_path)
    print(f"\nLoaded {len(df)} trades from {enriched_data_path}")

    # Verify data has expected structure
    assert "execution_timeframe" in df.columns
    assert "strategy_archetype" in df.columns
    assert "pnl" in df.columns
    assert "r_multiple" in df.columns

    # Create temp directory for models
    with tempfile.TemporaryDirectory() as tmpdir:
        model_dir = Path(tmpdir)

        # Initialize registry
        registry = ModelRegistry(model_dir=model_dir)

        # Train profitability models
        print("\nTraining profitability models...")
        prof_models = registry.train_all_profitability_models(df)

        if len(prof_models) == 0:
            pytest.skip(
                "Insufficient data to train profitability models "
                "(need 50+ trades per context)"
            )

        print(f"Trained {len(prof_models)} profitability models:")
        for key in prof_models.keys():
            print(f"  - {key}")

        # Train diagnostic models
        print("\nTraining diagnostic models...")
        contexts = df[["execution_timeframe", "strategy_archetype"]].drop_duplicates()
        diag_count = 0

        for _, row in contexts.iterrows():
            model = PerformanceDiagnosticModel(
                timeframe=row["execution_timeframe"],
                archetype=row["strategy_archetype"],
            )
            try:
                model.fit(df)
                registry.register_model("diagnostic", model.get_model_key(), model)
                diag_count += 1
            except ValueError:
                pass

        if diag_count == 0:
            pytest.skip(
                "Insufficient data to train diagnostic models "
                "(need 50+ trades per context)"
            )

        print(f"Trained {diag_count} diagnostic models")

        # Save models
        print("\nSaving models...")
        registry.save()

        # Verify files were created
        prof_dir = model_dir / "profitability"
        assert prof_dir.exists()
        prof_files = list(prof_dir.glob("*.pkl"))
        assert len(prof_files) == len(prof_models)
        print(f"Saved {len(prof_files)} profitability model files")

        diag_dir = model_dir / "diagnostic"
        assert diag_dir.exists()
        diag_files = list(diag_dir.glob("*.pkl"))
        assert len(diag_files) == diag_count
        print(f"Saved {len(diag_files)} diagnostic model files")

        # Load models in new registry
        print("\nLoading models...")
        new_registry = ModelRegistry(model_dir=model_dir)
        new_registry.load()

        loaded_prof = new_registry.list_models("profitability")
        loaded_diag = new_registry.list_models("diagnostic")

        assert len(loaded_prof) == len(prof_models)
        assert len(loaded_diag) == diag_count
        print(f"Loaded {len(loaded_prof)} profitability models")
        print(f"Loaded {len(loaded_diag)} diagnostic models")

        # Make predictions
        print("\nMaking predictions...")
        test_sample = df.head(10)

        for key in loaded_prof:
            # Parse key to get timeframe and archetype
            parts = key.split("_", 1)
            if len(parts) != 2:
                continue
            timeframe, archetype = parts

            # Filter test data for this context
            context_data = test_sample[
                (test_sample["execution_timeframe"] == timeframe)
                & (test_sample["strategy_archetype"] == archetype)
            ]

            if len(context_data) == 0:
                continue

            # Predict profitability
            predictions = new_registry.predict_profitability(
                X=context_data, timeframe=timeframe, archetype=archetype
            )
            proba = new_registry.predict_profitability_proba(
                X=context_data, timeframe=timeframe, archetype=archetype
            )

            assert len(predictions) == len(context_data)
            assert len(proba) == len(context_data)
            assert all(p in [0, 1] for p in predictions)
            print(f"  {key}: {len(predictions)} predictions")

        # Test diagnostic predictions
        for key in loaded_diag:
            model = new_registry.get_model("diagnostic", key)
            if model is None:
                continue

            # Parse key
            parts = key.split("_", 1)
            if len(parts) != 2:
                continue
            timeframe, archetype = parts

            # Filter test data
            context_data = test_sample[
                (test_sample["execution_timeframe"] == timeframe)
                & (test_sample["strategy_archetype"] == archetype)
            ]

            if len(context_data) == 0:
                continue

            # Predict quintiles
            quintiles = model.predict(context_data)
            assert len(quintiles) == len(context_data)
            assert all(q in [0, 1, 2, 3, 4] for q in quintiles)
            print(f"  {key}: quintiles={quintiles}")

        print("\n✅ Integration test passed!")


def test_individual_model_with_real_data(enriched_data_path):
    """Test individual ProfitabilityModel with real data."""
    df = pd.read_parquet(enriched_data_path)

    # Get first context
    first_context = df.iloc[0]
    timeframe = first_context["execution_timeframe"]
    archetype = first_context["strategy_archetype"]

    # Filter data for this context
    context_df = df[
        (df["execution_timeframe"] == timeframe)
        & (df["strategy_archetype"] == archetype)
    ]

    if len(context_df) < 50:
        pytest.skip(f"Insufficient data for {timeframe}_{archetype}")

    # Train individual model
    model = ProfitabilityModel(timeframe=timeframe, archetype=archetype)
    model.fit(context_df)

    # Make predictions
    predictions = model.predict(context_df.head(5))
    proba = model.predict_proba(context_df.head(5))

    assert len(predictions) == 5
    assert len(proba) == 5
    assert all(p in [0, 1] for p in predictions)

    print(f"\n✅ Individual model test passed for {timeframe}_{archetype}")

"""
This module defines the automated model training pipeline for the AI Lab.
"""

from pathlib import Path
from typing import Any, Dict, Tuple, cast

import joblib
import lightgbm as lgb
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV

from trading_platform.ai.data_connectors import AIDataConnector, DataCatalog
from trading_platform.ai.data_labeling import DataLabeler
from trading_platform.ai.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
)


class AITrainingPipeline:
    """
    Orchestrates the end-to-end model training process, from data loading
    to artifact storage.
    """

    def __init__(self, config_path: str):
        """
        Initializes the training pipeline with a given configuration.

        Args:
            config_path: Path to the YAML configuration file for the training run.
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.run_id = self.config.get("run_id", "default_run")
        self.artifacts_path = (
            Path(self.config.get("artifacts_base_path", "artifacts")) / self.run_id
        )
        self.artifacts_path.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        """Loads the YAML configuration file."""
        print(f"Loading configuration from: {self.config_path}")
        with open(self.config_path) as f:
            return cast(Dict[str, Any], yaml.safe_load(f))

    def _load_and_prepare_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Loads data using AIDataConnector, generates features, and creates labels.
        """
        print("Step 1: Loading and preparing data...")

        # 1. Load raw data
        data_config = self.config["data"]
        # In a real scenario, the DataCatalog would be a singleton or injected.
        connector = AIDataConnector(DataCatalog())
        raw_df = connector.load_training_data(**data_config)

        # 2. Generate features
        feature_config = self.config["features"]
        feature_pipeline = FeatureEngineeringPipeline(raw_df)
        featured_df = feature_pipeline.run(feature_config)

        # 3. Generate labels
        labeling_config = self.config["labeling"]
        labeler = DataLabeler(**labeling_config)
        labels = labeler.generate_future_price_direction(featured_df)

        # 4. Align features (X) and labels (y)
        # This ensures that we don't have look-ahead bias and that the data
        # used for training corresponds to the correct target label.
        X = featured_df.loc[labels.index]
        y = labels

        # Ensure no NaN values remain in the features after alignment
        X.dropna(inplace=True)
        y = y.loc[X.index]

        print(
            f"Data preparation complete. Shape of X: {X.shape}, Shape of y: {y.shape}"
        )
        return X, y

    def _train_model(self, X: pd.DataFrame, y: pd.Series) -> Any:
        """
        Initializes, trains, and optionally performs hyperparameter tuning
        for the specified model.
        """
        print(f"Step 2: Training model ({self.config['model']['type']})...")
        model_config = self.config["model"]
        model_type = model_config["type"]

        if model_type == "lightgbm":
            model = lgb.LGBMClassifier(**model_config.get("params", {}))
        elif model_type == "random_forest":
            model = RandomForestClassifier(**model_config.get("params", {}))
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        # Optional: Hyperparameter Tuning
        if "tuning" in model_config:
            tuning_config = model_config["tuning"]
            print(f"Performing GridSearchCV for {model_type}...")
            grid = GridSearchCV(
                model,
                param_grid=tuning_config["param_grid"],
                **tuning_config.get("settings", {}),
            )
            grid.fit(X, y)
            best_model = grid.best_estimator_
            print(f"Best parameters found: {grid.best_params_}")
        else:
            model.fit(X, y)
            best_model = model

        print("Model training complete.")
        return best_model

    def _save_artifacts(self, model: Any):
        """
        Saves the trained model and other run artifacts.
        """
        print(f"Step 3: Saving artifacts to {self.artifacts_path}...")

        # Save the trained model
        model_path = self.artifacts_path / "model.joblib"
        joblib.dump(model, model_path)
        print(f"Model saved to {model_path}")

        # Save the config used for the run
        config_snapshot_path = self.artifacts_path / "run_config.yaml"
        with open(config_snapshot_path, "w") as f:
            yaml.dump(self.config, f)
        print(f"Config snapshot saved to {config_snapshot_path}")

        # In a real implementation, we would also save:
        # - Evaluation metrics
        # - SHAP values / interpretability reports
        # - A summary of the run

    def run(self):
        """
        Executes the full training pipeline.
        """
        print(f"--- Starting AI Training Pipeline for Run ID: {self.run_id} ---")
        X, y = self._load_and_prepare_data()
        trained_model = self._train_model(X, y)
        self._save_artifacts(trained_model)
        print(f"--- Pipeline finished for Run ID: {self.run_id} ---")


if __name__ == "__main__":
    # This is an example of how the pipeline could be run.
    # A sample config would need to be created at 'sample_training_config.yaml'

    # Create a dummy config for demonstration
    dummy_config = {
        "run_id": "lgbm_test_run_002",
        "artifacts_base_path": "artifacts/training_runs",
        "data": {
            "symbol": "EURUSD",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
        },
        "features": [
            {"kind": "sma", "length": 10},
            {"kind": "rsi", "length": 14},
        ],
        "labeling": {"look_ahead_bars": 5},
        "model": {
            "type": "lightgbm",
            "params": {"n_estimators": 100, "random_state": 42},
            "tuning": {
                "param_grid": {"n_estimators": [50, 100], "learning_rate": [0.05, 0.1]},
                "settings": {"cv": 3, "scoring": "accuracy"},
            },
        },
    }
    DUMMY_CONFIG_PATH = "sample_training_config.yaml"
    with open(DUMMY_CONFIG_PATH, "w") as f:
        yaml.dump(dummy_config, f)

    pipeline = AITrainingPipeline(config_path=DUMMY_CONFIG_PATH)
    pipeline.run()
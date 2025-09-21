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

# Assuming placeholder classes from previous tasks exist
# from trading_platform.ai.data_connectors import AIDataConnector
# from trading_platform.ai.feature_engineering.pipeline import (
#     FeatureEngineeringPipeline,
# )
# from trading_platform.ai.data_labeling import DataLabeler


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
        Placeholder for loading data using AIDataConnector, generating features,
        and creating labels.
        """
        print("Step 1: Loading and preparing data...")
        # 1. Use AIDataConnector to get raw data (placeholder)
        # raw_data = AIDataConnector.get_data(self.config['data_source'])

        # 2. Use FeatureEngineeringPipeline to create features (placeholder)
        # features = FeatureEngineeringPipeline.run(raw_data, self.config['features'])

        # 3. Use DataLabeler to create the target variable (placeholder)
        # labels = DataLabeler.generate_labels(raw_data, self.config['labeling'])

        # Placeholder data for demonstration
        X = pd.DataFrame(
            {"feature1": range(100), "feature2": [x * 2 for x in range(100)]}
        )
        y = pd.Series([0, 1] * 50)
        print("Data preparation complete.")
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
        "run_id": "lgbm_test_run_001",
        "artifacts_base_path": "artifacts/training_runs",
        "data_source": {"name": "my_data", "version": "1.0"},
        "features": ["feature1", "feature2"],
        "labeling": {"method": "future_price_direction", "horizon": 5},
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

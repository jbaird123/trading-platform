"""
This module defines the automated model training pipeline for the AI Lab.
"""

import json  # Added this line
import os
from pathlib import Path
from typing import Any, Dict, Tuple, cast

import mlflow
import pandas as pd
import yaml
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV

from trading_platform.ai.data_connectors import AIDataConnector, DataCatalog
from trading_platform.ai.data_labeling import DataLabeler
from trading_platform.ai.evaluation.procedure import AIEvaluationProcedure
from trading_platform.ai.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
)
from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine

# Conditional import for type checking
# In a real implementation, you would have a more robust way to handle this
# or ensure lightgbm is always available in the environment.
try:
    import lightgbm as lgb
except ImportError:
    lgb = None


def _flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, Any]:
    """Flattens a nested dictionary for MLflow logging."""
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


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

        # Set up MLflow tracking URI
        tracking_uri = self.config.get("mlflow_tracking_uri", "./mlruns")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(self.config.get("experiment_name", "Default"))

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

        print(f"--- DEBUG: raw_df shape: {raw_df.shape}")
        print(f"--- DEBUG: featured_df shape: {featured_df.shape}")
        print(f"--- DEBUG: labels shape: {labels.shape}")

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
            if lgb is None:
                raise ImportError("LightGBM is not installed or cannot be imported.")
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
            mlflow.log_params(grid.best_params_)
        else:
            model.fit(X, y)
            best_model = model

        print("Model training complete.")
        return best_model

    def _evaluate_and_log_artifacts(self, model: Any, X: pd.DataFrame, y: pd.Series):
        """
        Evaluates the model and logs all artifacts to MLflow.
        """
        print("Step 3: Evaluating model and logging artifacts...")

        metrics: Dict[str, Any] = {}
        eval_config = self.config.get("evaluation", {})
        if eval_config:
            evaluator = AIEvaluationProcedure(config=eval_config)
            metrics = evaluator.run(model, X, y)
            # MLflow prefers flat metrics dictionary
            flat_metrics = _flatten_dict(metrics)
            mlflow.log_metrics(flat_metrics)
            print(f"Logged metrics: {flat_metrics}")

        # 2. Log model
        model_info = mlflow.sklearn.log_model(model, "model")
        print(f"Model saved to MLflow: {model_info.model_uri}")

        # 3. Convert and Log ONNX model
        print("Converting model to ONNX and logging...")
        # Infer input types from the training data X
        initial_type = [("float_input", FloatTensorType([None, X.shape[1]]))]  # type: ignore
        onnx_model = convert_sklearn(model, initial_types=initial_type)

        # Save ONNX model to a temporary file
        onnx_path = "model.onnx"
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())

        # Log ONNX model as an MLflow artifact
        mlflow.log_artifact(onnx_path, "onnx_model")
        print(f"ONNX model saved to MLflow: {onnx_path}")
        os.remove(onnx_path)  # Clean up temporary file

        # 4. Run Diagnostic Synthesis Engine
        print("Running Diagnostic Synthesis Engine...")
        synthesis_engine = DiagnosticSynthesisEngine(
            analysis_data={
                "metrics": metrics,
                "synthesis_config": self.config.get("synthesis", {}),
                "model": model,
                "X": X,
                "y": y,
            }
        )
        synthesis_engine.run()  # Call run without arguments
        synthesis_results = json.loads(
            synthesis_engine.generate_report_json()
        )  # Get results
        print(f"Diagnostic Synthesis Engine results: {synthesis_results}")
        mlflow.log_dict(synthesis_results, "diagnostic_synthesis_results.json")

    def run(self):
        """
        Executes the full training pipeline within an MLflow run context.
        """
        with mlflow.start_run(run_name=self.run_id) as run:
            print(
                f"--- Starting AI Training Pipeline for Run ID: {run.info.run_id} ---"
            )
            mlflow.log_params(_flatten_dict(self.config))

            X, y = self._load_and_prepare_data()
            trained_model = self._train_model(X, y)
            self._evaluate_and_log_artifacts(trained_model, X, y)

            print(f"--- Pipeline finished for Run ID: {run.info.run_id} ---")


def main():
    """Main function to run the training pipeline from the command line."""
    # This is an example of how the pipeline could be run.
    # A sample config would need to be created at 'sample_training_config.yaml'

    # Create a dummy config for demonstration
    dummy_config = {
        "run_id": "lgbm_test_run_003",
        "experiment_name": "AI Lab Demo",
        "data": {
            "symbol": "EURUSD",
            "timeframe": "1D",
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
        },
        "features": [{"kind": "sma", "length": 10}, {"kind": "rsi", "length": 14}],
        "labeling": {"look_ahead_bars": 5},
        "model": {
            "type": "lightgbm",
            "params": {"n_estimators": 100, "random_state": 42},
        },
        "evaluation": {
            "run_cross_validation": True,
            "cross_validation": {"n_splits": 5},
        },
    }
    DUMMY_CONFIG_PATH = "sample_training_config.yaml"
    with open(DUMMY_CONFIG_PATH, "w") as f:
        yaml.dump(dummy_config, f)

    pipeline = AITrainingPipeline(config_path=DUMMY_CONFIG_PATH)
    pipeline.run()


if __name__ == "__main__":
    main()

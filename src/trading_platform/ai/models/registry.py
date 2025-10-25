"""ModelRegistry - Central manager for profitability and diagnostic models.

This module provides a registry for managing multiple specialized ML models:
- Profitability models: One per timeframe/archetype for signal filtering
- Diagnostic models: One per timeframe/archetype for regime analysis

The registry supports:
- Model registration and retrieval
- Lazy model instantiation
- Batch training from enriched data
- Model persistence (save/load)
- Routing predictions to appropriate models
"""

import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from trading_platform.ai.models.profitability import ProfitabilityModel


class ModelRegistry:
    """Central registry for managing specialized ML models.

    The registry maintains two separate model families:
    1. Profitability models: Binary classifiers for signal filtering (no lookahead)
    2. Diagnostic models: Quintile classifiers for regime analysis (with lookahead)

    Each family contains multiple specialized models, one per timeframe/archetype combination.
    """

    def __init__(self, model_dir: Path | None = None):
        """Initialize ModelRegistry.

        Args:
            model_dir: Directory for model storage. Defaults to models/ in project root.
        """
        if model_dir is None:
            model_dir = Path("models")

        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Separate registries for each model family
        self._profitability_models: dict[str, ProfitabilityModel] = {}
        self._diagnostic_models: dict[
            str, Any
        ] = {}  # Will use PerformanceDiagnosticModel later

    def register_model(self, family: str, key: str, model: Any) -> None:
        """Register a model in the specified family.

        Args:
            family: Model family ("profitability" or "diagnostic")
            key: Unique identifier (e.g., "5min_trend_following")
            model: Model instance to register

        Raises:
            ValueError: If key already registered or family is invalid
        """
        if family == "profitability":
            if key in self._profitability_models:
                raise ValueError(
                    f"Model key '{key}' already registered in profitability family"
                )
            self._profitability_models[key] = model
        elif family == "diagnostic":
            if key in self._diagnostic_models:
                raise ValueError(
                    f"Model key '{key}' already registered in diagnostic family"
                )
            self._diagnostic_models[key] = model
        else:
            raise ValueError(
                f"Invalid model family: {family}. Must be 'profitability' or 'diagnostic'"
            )

    def get_model(self, family: str, key: str) -> Any | None:
        """Retrieve a model by family and key.

        Args:
            family: Model family ("profitability" or "diagnostic")
            key: Model identifier

        Returns:
            Model instance if found, None otherwise
        """
        if family == "profitability":
            return self._profitability_models.get(key)
        elif family == "diagnostic":
            return self._diagnostic_models.get(key)
        else:
            return None

    def list_models(self, family: str) -> list[str]:
        """List all registered model keys in a family.

        Args:
            family: Model family ("profitability" or "diagnostic")

        Returns:
            List of model keys
        """
        if family == "profitability":
            return list(self._profitability_models.keys())
        elif family == "diagnostic":
            return list(self._diagnostic_models.keys())
        else:
            return []

    def get_or_create_profitability_model(
        self,
        timeframe: str,
        archetype: str,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> ProfitabilityModel:
        """Get existing profitability model or create new one.

        Args:
            timeframe: Execution timeframe (e.g., "5min", "15min")
            archetype: Strategy archetype (e.g., "trend_following")
            n_estimators: Number of trees (only used if creating new model)
            random_state: Random seed (only used if creating new model)

        Returns:
            ProfitabilityModel instance (existing or newly created)
        """
        key = f"{timeframe}_{archetype}"
        model = self.get_model("profitability", key)

        if model is None:
            # Create new model
            model = ProfitabilityModel(
                timeframe=timeframe,
                archetype=archetype,
                n_estimators=n_estimators,
                random_state=random_state,
            )
            self.register_model("profitability", key, model)

        return model

    def train_all_profitability_models(
        self,
        enriched_trades_df: pd.DataFrame,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> dict[str, ProfitabilityModel]:
        """Train profitability models for all contexts in the data.

        Args:
            enriched_trades_df: DataFrame with enriched trade data
            n_estimators: Number of trees in RandomForestClassifier
            random_state: Random seed for reproducibility

        Returns:
            Dictionary of trained models {key: model}
        """
        # Find all unique contexts
        contexts = enriched_trades_df[
            ["execution_timeframe", "strategy_archetype"]
        ].drop_duplicates()

        trained_models = {}

        for _, row in contexts.iterrows():
            timeframe = row["execution_timeframe"]
            archetype = row["strategy_archetype"]
            key = f"{timeframe}_{archetype}"

            # Get or create model
            model = self.get_or_create_profitability_model(
                timeframe=timeframe,
                archetype=archetype,
                n_estimators=n_estimators,
                random_state=random_state,
            )

            # Try to train
            try:
                model.fit(enriched_trades_df)
                trained_models[key] = model
            except ValueError as e:
                # Skip contexts with insufficient data
                warnings.warn(f"Skipping {key}: {e}")
                continue

        return trained_models

    def predict_profitability(
        self, X: pd.DataFrame, timeframe: str, archetype: str
    ) -> pd.Series:
        """Predict profitability using the appropriate model.

        Args:
            X: DataFrame with trade features
            timeframe: Execution timeframe
            archetype: Strategy archetype

        Returns:
            Series of predictions (0=unprofitable, 1=profitable)

        Raises:
            ValueError: If model not found
        """
        key = f"{timeframe}_{archetype}"
        model = self.get_model("profitability", key)

        if model is None:
            raise ValueError(f"Profitability model '{key}' not found. Train it first.")

        predictions = model.predict(X)
        return pd.Series(predictions, index=X.index)

    def predict_profitability_proba(
        self, X: pd.DataFrame, timeframe: str, archetype: str
    ) -> pd.DataFrame:
        """Predict profitability probabilities using the appropriate model.

        Args:
            X: DataFrame with trade features
            timeframe: Execution timeframe
            archetype: Strategy archetype

        Returns:
            DataFrame with columns [prob_unprofitable, prob_profitable]

        Raises:
            ValueError: If model not found
        """
        key = f"{timeframe}_{archetype}"
        model = self.get_model("profitability", key)

        if model is None:
            raise ValueError(f"Profitability model '{key}' not found. Train it first.")

        proba = model.predict_proba(X)
        return pd.DataFrame(
            proba, columns=["prob_unprofitable", "prob_profitable"], index=X.index
        )

    def save(self) -> None:
        """Save all models to disk.

        Models are saved in separate directories:
        - {model_dir}/profitability/{key}.pkl
        - {model_dir}/diagnostic/{key}.pkl
        """
        # Save profitability models
        prof_dir = self.model_dir / "profitability"
        prof_dir.mkdir(parents=True, exist_ok=True)

        for key, model in self._profitability_models.items():
            if model.model is not None:  # Only save fitted models
                path = prof_dir / f"{key}.pkl"
                model.save(path)

        # Save diagnostic models (when implemented)
        diag_dir = self.model_dir / "diagnostic"
        diag_dir.mkdir(parents=True, exist_ok=True)

        for key, model in self._diagnostic_models.items():
            # For now, assume diagnostic models have same interface
            if hasattr(model, "model") and model.model is not None:
                path = diag_dir / f"{key}.pkl"
                model.save(path)

    def load(self) -> None:
        """Load all models from disk.

        Discovers and loads models from:
        - {model_dir}/profitability/*.pkl
        - {model_dir}/diagnostic/*.pkl
        """
        # Load profitability models
        prof_dir = self.model_dir / "profitability"
        if prof_dir.exists():
            for model_path in prof_dir.glob("*.pkl"):
                key = model_path.stem  # Filename without extension
                model = ProfitabilityModel.load(model_path)
                self._profitability_models[key] = model

        # Load diagnostic models (when implemented)
        diag_dir = self.model_dir / "diagnostic"
        if diag_dir.exists():
            for model_path in diag_dir.glob("*.pkl"):
                key = model_path.stem
                # TODO: Load PerformanceDiagnosticModel when implemented
                # model = PerformanceDiagnosticModel.load(model_path)
                # self._diagnostic_models[key] = model
                pass

    def get_model_path(self, family: str, key: str) -> Path:
        """Get the filesystem path for a model.

        Args:
            family: Model family ("profitability" or "diagnostic")
            key: Model identifier

        Returns:
            Path where model is/should be stored
        """
        return self.model_dir / family / f"{key}.pkl"

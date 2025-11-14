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

import logging
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.ai.feature_engineering.unpacking import unpack_simulated_holds
from trading_platform.ai.models.performance_diagnostic import PerformanceDiagnosticModel
from trading_platform.ai.models.profitability import ProfitabilityModel
from trading_platform.ai.models.profitability_classifier import (
    ProfitabilityClassifierModel,
)


class ModelRegistry:
    """Central registry for managing specialized ML models.

    The registry maintains two separate model families:
    1. Profitability models: R-multiple regressors for signal filtering (no lookahead)
    2. Diagnostic models: Quintile classifiers for regime analysis (with lookahead)
       - Supports segregated training by data availability
       - Models keyed with suffixes: _rmultiple, _pnl_with_risk, _pnl_no_risk

    Each family contains multiple specialized models, one per
    timeframe/archetype combination.
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
        self._profitability_classifier_models: dict[
            str, ProfitabilityClassifierModel
        ] = {}
        self._diagnostic_models: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    def register_model(self, family: str, key: str, model: Any) -> None:
        """Register a model in the specified family.

        Args:
            family: Model family
                ("profitability", "profitability_classifier", or "diagnostic")
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
            prof_model = cast(ProfitabilityModel, model)
            self._profitability_models[key] = prof_model
        elif family == "profitability_classifier":
            if key in self._profitability_classifier_models:
                raise ValueError(
                    f"Model key '{key}' already registered in "
                    "profitability_classifier family"
                )
            classifier_model = cast(ProfitabilityClassifierModel, model)
            self._profitability_classifier_models[key] = classifier_model
        elif family == "diagnostic":
            if key in self._diagnostic_models:
                raise ValueError(
                    f"Model key '{key}' already registered in diagnostic family"
                )
            self._diagnostic_models[key] = model
        else:
            raise ValueError(
                "Invalid model family: "
                f"{family}. Must be one of 'profitability', "
                "'profitability_classifier', or 'diagnostic'"
            )

    def get_model(self, family: str, key: str) -> Any | None:
        """Retrieve a model by family and key.

        Args:
            family: Model family
                ("profitability", "profitability_classifier", or "diagnostic")
            key: Model identifier

        Returns:
            Model instance if found, None otherwise
        """
        if family == "profitability":
            return self._profitability_models.get(key)
        elif family == "profitability_classifier":
            return self._profitability_classifier_models.get(key)
        elif family == "diagnostic":
            return self._diagnostic_models.get(key)
        else:
            return None

    def list_models(self, family: str) -> list[str]:
        """List all registered model keys in a family.

        Args:
            family: Model family
                ("profitability", "profitability_classifier", or "diagnostic")

        Returns:
            List of model keys
        """
        if family == "profitability":
            return list(self._profitability_models.keys())
        elif family == "profitability_classifier":
            return list(self._profitability_classifier_models.keys())
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

    def get_or_create_profitability_classifier(
        self,
        timeframe: str,
        archetype: str,
        random_state: int = 42,
    ) -> ProfitabilityClassifierModel:
        key = f"{timeframe}_{archetype}"
        model = self.get_model("profitability_classifier", key)

        if model is None:
            model = ProfitabilityClassifierModel(
                timeframe=timeframe,
                archetype=archetype,
                random_state=random_state,
            )
            self.register_model("profitability_classifier", key, model)

        return model

    def train_all_profitability_models(
        self,
        enriched_trades_df: pd.DataFrame,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> dict[str, ProfitabilityModel]:
        """Train profitability models for all contexts in the data.

        Profitability models require r_multiple values, so only trades from
        campaigns with risk management (stop losses) are used for training.

        Args:
            enriched_trades_df: DataFrame with enriched trade data
            n_estimators: Number of trees in RandomForestRegressor
            random_state: Random seed for reproducibility

        Returns:
            Dictionary of trained models {key: model}
        """
        # Filter to only trades with r_multiple (from campaigns with risk management)
        # Profitability models predict r_multiple, so they can only train on trades
        # that have defined stop losses
        trades_with_risk = enriched_trades_df[
            enriched_trades_df["r_multiple"].notnull()
        ].copy()

        if len(trades_with_risk) == 0:
            raise ValueError(
                "No trades with r_multiple found. Profitability models require "
                "trades from campaigns with risk management (stop losses)."
            )

        # Find all unique contexts in the filtered data
        contexts = trades_with_risk[
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

            # Train model on filtered data (only trades with r_multiple)
            model.fit(trades_with_risk)
            trained_models[key] = model

        return trained_models

    def train_all_diagnostic_from_enriched(
        self,
        enriched_df: pd.DataFrame,
        min_trades: int = 50,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> dict[str, PerformanceDiagnosticModel]:
        """Train diagnostic models for all contexts from enriched trade data.

        This method unpacks the nested post_exit_analysis_simulated_holds column
        before training, ensuring all features are available to the model.

        Args:
            enriched_df: DataFrame with enriched trade data including
                post-trade analysis
            min_trades: Minimum trades required per context (default: 50)
            n_estimators: Number of trees in RandomForestClassifier
            random_state: Random seed for reproducibility

        Returns:
            Dictionary of trained models {key: model}

        Raises:
            ValueError: If any context has insufficient data
        """
        # First, unpack the nested analysis data into flat features
        enriched_df = unpack_simulated_holds(enriched_df)

        # Find all unique contexts
        contexts = enriched_df[
            ["execution_timeframe", "strategy_archetype"]
        ].drop_duplicates()

        trained_models = {}

        for _, row in contexts.iterrows():
            timeframe = row["execution_timeframe"]
            archetype = row["strategy_archetype"]
            key = f"{timeframe}_{archetype}"

            # Create diagnostic model
            model = PerformanceDiagnosticModel(
                timeframe=timeframe,
                archetype=archetype,
                n_estimators=n_estimators,
                random_state=random_state,
            )

            # Train model - will raise error if insufficient data
            model.fit(enriched_df)

            # Register and store
            self.register_model("diagnostic", key, model)
            trained_models[key] = model

        return trained_models

    def train_all_diagnostic_models(
        self,
        enriched_df: pd.DataFrame,
        min_trades: int = 50,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> dict[str, PerformanceDiagnosticModel]:
        """Train diagnostic models with segregated training by data availability.

        Implements segregated training strategy:
        - For trades with r_multiple: train r_multiple model
        - For trades without r_multiple but with pnl: train pnl_no_risk model
        - Keys include suffix: e.g., "5min_trend_following_rmultiple"

        Args:
            enriched_df: DataFrame with enriched trade data including
                post-trade analysis
            min_trades: Minimum trades required per partition (default: 50)
            n_estimators: Number of trees in RandomForestClassifier
            random_state: Random seed for reproducibility

        Returns:
            Dictionary of trained models {key: model}

        Raises:
            ValueError: If any partition has insufficient data
        """
        # First, unpack the nested analysis data into flat features
        enriched_df = unpack_simulated_holds(enriched_df)

        # Find all unique contexts
        contexts = enriched_df[
            ["execution_timeframe", "strategy_archetype"]
        ].drop_duplicates()

        trained_models = {}

        for _, row in contexts.iterrows():
            timeframe = row["execution_timeframe"]
            archetype = row["strategy_archetype"]
            base_key = f"{timeframe}_{archetype}"

            # Filter by context
            context_df = enriched_df[
                (enriched_df["execution_timeframe"] == timeframe)
                & (enriched_df["strategy_archetype"] == archetype)
            ].copy()

            # Partition 1: Trades with r_multiple (can train r_multiple model)
            df_with_risk = context_df[context_df["r_multiple"].notna()].copy()

            if len(df_with_risk) >= min_trades:
                model_key = f"{base_key}_rmultiple"
                model = PerformanceDiagnosticModel(
                    timeframe=timeframe,
                    archetype=archetype,
                    target_metric="r_multiple",
                    n_estimators=n_estimators,
                    random_state=random_state,
                )
                model.fit(df_with_risk)
                self.register_model("diagnostic", model_key, model)
                trained_models[model_key] = model

            # Partition 2: Trades without r_multiple (can train pnl_no_risk model)
            df_no_risk = context_df[context_df["r_multiple"].isna()].copy()

            if len(df_no_risk) >= min_trades:
                model_key = f"{base_key}_pnl_no_risk"
                model = PerformanceDiagnosticModel(
                    timeframe=timeframe,
                    archetype=archetype,
                    target_metric="pnl",
                    n_estimators=n_estimators,
                    random_state=random_state,
                )
                model.fit(df_no_risk)
                self.register_model("diagnostic", model_key, model)
                trained_models[model_key] = model

        return trained_models

    def analyze_performance_regime(
        self,
        X: pd.DataFrame,
        timeframe: str,
        archetype: str,
        model_suffix: str | None = None,
    ) -> pd.Series:
        """Analyze performance regime with context-aware guardrails.

        Args:
            X: DataFrame with trade features (including lookahead, must include
                'entry_time')
            timeframe: Execution timeframe
            archetype: Strategy archetype
            model_suffix: Model suffix (e.g., "_rmultiple", "_pnl_no_risk").
                If None, auto-detects based on data

        Returns:
            Series of quintile predictions (0-4)

        Raises:
            ValueError: If model not found, data type mismatch, or lookahead bias
                detected
        """
        # Auto-detect model suffix if not provided
        if model_suffix is None:
            # Check if data has r_multiple
            if "r_multiple" in X.columns and X["r_multiple"].notna().any():
                model_suffix = "_rmultiple"
            else:
                model_suffix = "_pnl_no_risk"

        key = f"{timeframe}_{archetype}{model_suffix}"
        model = self.get_model("diagnostic", key)

        if model is None:
            raise ValueError(f"Diagnostic model '{key}' not found. Train it first.")

        # Validate data type matches model
        has_risk_data = "r_multiple" in X.columns and X["r_multiple"].notna().any()

        if "_rmultiple" in model_suffix and not has_risk_data:
            raise ValueError(
                f"Data type mismatch: Model '{key}' expects r_multiple data, "
                f"but input data has no r_multiple values."
            )

        if "_no_risk" in model_suffix and has_risk_data:
            raise ValueError(
                f"Data type mismatch: Model '{key}' was trained on data without "
                f"r_multiple, but input data has r_multiple values."
            )

        # Lookahead bias prevention: Check if prediction data overlaps with
        # training period
        if "entry_time" in X.columns and model.training_start_date_ is not None:
            input_times = pd.to_datetime(X["entry_time"])
            input_start = input_times.min()
            input_end = input_times.max()

            # Check for temporal overlap
            if (
                input_end >= model.training_start_date_
                and input_start <= model.training_end_date_
            ):
                raise ValueError(
                    f"Lookahead bias detected! Model '{key}' was trained on "
                    f"data from {model.training_start_date_} to "
                    f"{model.training_end_date_}, but prediction data spans "
                    f"{input_start} to {input_end}. These periods overlap, "
                    "which would use training data for predictions."
                )

        predictions = model.predict(X)
        result: pd.Series[Any] = pd.Series(predictions, index=X.index)
        return result

    def predict_profitability(
        self, X: pd.DataFrame, timeframe: str, archetype: str
    ) -> pd.Series:
        """Predict R-multiple using the appropriate model.

        Args:
            X: DataFrame with trade features (must include 'entry_time' column)
            timeframe: Execution timeframe
            archetype: Strategy archetype

        Returns:
            Series of R-multiple predictions (continuous values)

        Raises:
            ValueError: If model not found or lookahead bias detected
        """
        key = f"{timeframe}_{archetype}"
        model = self.get_model("profitability", key)

        if model is None:
            raise ValueError(f"Profitability model '{key}' not found. Train it first.")

        # Lookahead bias prevention: Check if prediction data overlaps with
        # training period
        if "entry_time" in X.columns and model.training_start_date_ is not None:
            input_times = pd.to_datetime(X["entry_time"])
            input_start = input_times.min()
            input_end = input_times.max()

            # Check for temporal overlap
            if (
                input_end >= model.training_start_date_
                and input_start <= model.training_end_date_
            ):
                raise ValueError(
                    f"Lookahead bias detected! Model '{key}' was trained on "
                    f"data from {model.training_start_date_} to "
                    f"{model.training_end_date_}, but prediction data spans "
                    f"{input_start} to {input_end}. These periods overlap, "
                    "which would use training data for predictions."
                )

        predictions = model.predict(X)
        result: pd.Series[Any] = pd.Series(predictions, index=X.index)
        return result

    def save(self) -> None:
        """Save all models to disk.

        Models are saved in separate directories:
        - {model_dir}/profitability/{key}.pkl
        - {model_dir}/profitability_classifier/{key}.pkl
        - {model_dir}/diagnostic/{key}.pkl
        """
        # Save profitability models
        prof_dir = self.model_dir / "profitability"
        prof_dir.mkdir(parents=True, exist_ok=True)

        for key, model in self._profitability_models.items():
            if model.model is not None:  # Only save fitted models
                path = prof_dir / f"{key}.pkl"
                model.save(path)

        clf_dir = self.model_dir / "profitability_classifier"
        clf_dir.mkdir(parents=True, exist_ok=True)

        for key, classifier in self._profitability_classifier_models.items():
            if classifier.model is not None:
                path = clf_dir / f"{key}.pkl"
                classifier.save(path)

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
        - {model_dir}/profitability_classifier/*.pkl
        - {model_dir}/diagnostic/*.pkl
        """
        # Load profitability models
        prof_dir = self.model_dir / "profitability"
        if prof_dir.exists():
            for model_path in prof_dir.glob("*.pkl"):
                key = model_path.stem  # Filename without extension
                prof_model = ProfitabilityModel.load(model_path)
                self._profitability_models[key] = prof_model

        clf_dir = self.model_dir / "profitability_classifier"
        if clf_dir.exists():
            for model_path in clf_dir.glob("*.pkl"):
                key = model_path.stem
                try:
                    clf_model = ProfitabilityClassifierModel.load(model_path)
                except Exception as exc:  # pragma: no cover
                    self._logger.warning(
                        "Failed to load profitability classifier %s: %s",
                        model_path,
                        exc,
                    )
                    continue
                self._profitability_classifier_models[key] = clf_model

        # Load diagnostic models
        diag_dir = self.model_dir / "diagnostic"
        if diag_dir.exists():
            for model_path in diag_dir.glob("*.pkl"):
                key = model_path.stem
                try:
                    diag_model = PerformanceDiagnosticModel.load(model_path)
                except Exception as exc:  # pragma: no cover - defensive logging
                    self._logger.warning(
                        "Failed to load diagnostic model %s: %s", model_path, exc
                    )
                    continue
                self._diagnostic_models[key] = diag_model

    def get_model_path(self, family: str, key: str) -> Path:
        """Get the filesystem path for a model.

        Args:
            family: Model family
                ("profitability", "profitability_classifier", or "diagnostic")
            key: Model identifier

        Returns:
            Path where model is/should be stored
        """
        return self.model_dir / family / f"{key}.pkl"

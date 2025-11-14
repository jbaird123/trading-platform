"""ProfitabilityModel - Context-specific predictive models for signal filtering.

This module implements specialized profitability prediction models, one per
timeframe/archetype combination. Each model uses only entry-time features (no
lookahead) to predict whether a trade will be profitable, making them suitable
for real-time signal filtering.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer

from ._timeframe_utils import drop_lower_timeframe_global_features
from .feature_groups import (
    ENGINEERED_GROUP_PATTERNS,
    RISK_FEATURE_COLUMNS,
    add_normalized_risk_features,
    collect_group_patterns,
)

SELECTED_FEATURE_GROUPS: dict[tuple[str, str], tuple[str, ...]] = {
    ("5min", "trend_following"): ("calendar",),
    ("15min", "trend_following"): ("calendar",),
    ("1H", "trend_following"): ("alignment", "structure"),
    ("4H", "trend_following"): ("structure", "momentum"),
    ("1D", "trend_following"): ("volatility",),
}


class ProfitabilityModel:
    """Context-specific regressor for R-multiple prediction.

    Each model specializes in a specific timeframe/archetype combination and
    uses only features known at entry time (no lookahead). This ensures the
    model can be used in real-time for signal filtering.

    Features used:
    - All `context_at_entry_*` columns (market indicators at entry)
    - `side` (long/short) - one-hot encoded
    - `symbol` (currency pair) - one-hot encoded
    - Temporal features from `entry_time` (hour, day_of_week, trading session)

    Target: R-multiple (continuous risk-adjusted return)
    """

    def __init__(
        self,
        timeframe: str,
        archetype: str,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        """Initialize ProfitabilityModel for specific context.

        Args:
            timeframe: Execution timeframe (e.g., "5min", "15min", "1h")
            archetype: Strategy archetype (e.g., "trend_following", "mean_reversion")
            n_estimators: Number of trees in RandomForestRegressor
            random_state: Random seed for reproducibility
        """
        self.timeframe = timeframe
        self.archetype = archetype
        self.n_estimators = n_estimators
        self.random_state = random_state

        # Model components (initialized during fit)
        self.model: RandomForestRegressor | None = None
        self.feature_names_: list[str] | None = None
        self.imputer: SimpleImputer | None = None
        self.training_start_date_: pd.Timestamp | None = None
        self.training_end_date_: pd.Timestamp | None = None

    def fit(self, trades_df: pd.DataFrame) -> "ProfitabilityModel":
        """Train model on historical trades.

        Args:
            trades_df: DataFrame with enriched trade data containing:
                - execution_timeframe, strategy_archetype (for filtering)
                - context_at_entry_* columns (features)
                - side, symbol, entry_time (metadata features)
                - pnl (target)

        Returns:
            self (fitted model)

        Raises:
            ValueError: If insufficient data (< 50 trades for this context)
            KeyError: If required columns missing
        """
        # Validate input has data
        if len(trades_df) == 0:
            raise ValueError(
                f"Insufficient data: need 50+ trades for "
                f"{self.timeframe}_{self.archetype}, got 0"
            )

        # Filter data by context
        df = trades_df[
            (trades_df["execution_timeframe"] == self.timeframe)
            & (trades_df["strategy_archetype"] == self.archetype)
        ].copy()

        # Validate minimum samples
        if len(df) < 50:
            raise ValueError(
                f"Insufficient data: need 50+ trades for "
                f"{self.timeframe}_{self.archetype}, got {len(df)}"
            )

        # Validate r_multiple column exists and has no nulls (required for training)
        if "r_multiple" not in df.columns:
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: "
                f"Missing required column 'r_multiple'."
            )

        if df["r_multiple"].isnull().any():
            n_null = df["r_multiple"].isnull().sum()
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: "
                f"Cannot train without historical 'r_multiple' values. "
                f"Found {n_null} missing values."
            )

        # Validate initial_stop_loss_price exists and is valid
        # (required for predictions)
        if "initial_stop_loss_price" not in df.columns:
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: "
                f"Missing required column 'initial_stop_loss_price'."
            )

        if df["initial_stop_loss_price"].isnull().any():
            n_null = df["initial_stop_loss_price"].isnull().sum()
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: "
                f"All trades must have a valid 'initial_stop_loss_price'. "
                f"Found {n_null} null values."
            )

        # Record training date range (for lookahead bias prevention)
        self.training_start_date_ = pd.to_datetime(df["entry_time"]).min()
        self.training_end_date_ = pd.to_datetime(df["entry_time"]).max()

        # Drop global features below execution timeframe
        df = drop_lower_timeframe_global_features(df, self.timeframe)

        # Extract features (ONLY entry-time features - NO lookahead)
        X = self._extract_features(df)

        # Drop columns that are entirely NaN to avoid sklearn warnings.
        all_nan_columns = [col for col in X.columns if X[col].isnull().all()]
        if all_nan_columns:
            X = X.drop(columns=all_nan_columns)

        if X.empty:
            raise ValueError(
                f"No usable features available for {self.timeframe}_{self.archetype}."
            )

        # Create target: R-multiple regression
        y = df["r_multiple"].values

        # Store feature names for later alignment
        self.feature_names_ = X.columns.tolist()

        # Initialize and fit imputer (handle missing values)
        self.imputer = SimpleImputer(strategy="mean")
        X_imputed = self.imputer.fit_transform(X)

        # Initialize and fit model
        self.model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,  # Use all cores
        )
        self.model.fit(X_imputed, y)

        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict R-multiple (continuous risk-adjusted return).

        Args:
            X: DataFrame with trade features (same structure as training data)

        Returns:
            Array of R-multiple predictions (e.g., 2.5 means 2.5x risk,
            -1.0 means 1x loss)

        Raises:
            ValueError: If model not fitted
        """
        if self.model is None or self.imputer is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract and align features
        X_features = self._extract_features(X)
        X_aligned = self._align_features(X_features)

        # Impute missing values
        X_imputed = self.imputer.transform(X_aligned)

        # Type narrowing: we know model is fitted here
        predictions: np.ndarray = self.model.predict(X_imputed)
        return predictions

    def predict_with_confidence(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict R-multiple with confidence intervals.

        Uses individual tree predictions from the RandomForestRegressor to
        calculate prediction uncertainty. Returns a 95% confidence interval
        (mean ± 2*std).

        Args:
            X: DataFrame with trade features (same structure as training data)

        Returns:
            DataFrame with columns:
                - prediction: Mean R-multiple prediction across all trees
                - std: Standard deviation of tree predictions
                - lower_bound: prediction - 2*std (95% CI lower bound)
                - upper_bound: prediction + 2*std (95% CI upper bound)

        Raises:
            ValueError: If model not fitted
        """
        if self.model is None or self.imputer is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract and align features
        X_features = self._extract_features(X)
        X_aligned = self._align_features(X_features)

        # Impute missing values
        X_imputed = self.imputer.transform(X_aligned)

        # Get predictions from all individual trees
        all_tree_predictions = np.array(
            [tree.predict(X_imputed) for tree in self.model.estimators_]
        )

        # Calculate statistics across trees (axis=0 to aggregate across trees)
        predictions = all_tree_predictions.mean(axis=0)
        std = all_tree_predictions.std(axis=0)

        # Calculate 95% confidence interval (±2 std)
        return pd.DataFrame(
            {
                "prediction": predictions,
                "std": std,
                "lower_bound": predictions - 2 * std,
                "upper_bound": predictions + 2 * std,
            },
            index=X.index,
        )

    def save(self, path: Path) -> None:
        """Save model to disk.

        Args:
            path: Path to save model (.pkl file)
        """
        if self.model is None:
            raise ValueError("Cannot save unfitted model")

        model_data = {
            "model": self.model,
            "feature_names": self.feature_names_,
            "imputer": self.imputer,
            "timeframe": self.timeframe,
            "archetype": self.archetype,
            "training_start_date": self.training_start_date_,
            "training_end_date": self.training_end_date_,
            "hyperparams": {
                "n_estimators": self.n_estimators,
                "random_state": self.random_state,
            },
        }

        joblib.dump(model_data, path)

    @classmethod
    def load(cls, path: Path) -> "ProfitabilityModel":
        """Load model from disk.

        Args:
            path: Path to saved model (.pkl file)

        Returns:
            Loaded ProfitabilityModel instance
        """
        model_data = joblib.load(path)

        # Reconstruct instance
        instance = cls(
            timeframe=model_data["timeframe"],
            archetype=model_data["archetype"],
            n_estimators=model_data["hyperparams"]["n_estimators"],
            random_state=model_data["hyperparams"]["random_state"],
        )

        # Set fitted attributes
        instance.model = model_data["model"]
        instance.feature_names_ = model_data["feature_names"]
        instance.imputer = model_data["imputer"]
        # Handle backward compatibility for training dates
        instance.training_start_date_ = model_data.get("training_start_date")
        instance.training_end_date_ = model_data.get("training_end_date")

        return instance

    def get_model_key(self) -> str:
        """Get unique identifier for this model.

        Returns:
            String key in format: "{timeframe}_{archetype}"
        """
        return f"{self.timeframe}_{self.archetype}"

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract entry-time features from DataFrame.

        Args:
            df: Raw trades DataFrame

        Returns:
            DataFrame with only features known at entry time
        """
        df = df.copy()
        df = add_normalized_risk_features(df)

        features: list[str] = []

        group_names = SELECTED_FEATURE_GROUPS.get((self.timeframe, self.archetype))
        if group_names is not None:
            pattern_list = collect_group_patterns(group_names)
        else:
            pattern_list = [
                pattern
                for patterns in ENGINEERED_GROUP_PATTERNS.values()
                for pattern in patterns
            ]
        lowered_patterns = [pattern.lower() for pattern in pattern_list]

        entry_cols: list[str] = []
        for col in df.columns:
            if not col.startswith("context_at_entry_"):
                continue
            if col.startswith("context_at_entry_global_") and lowered_patterns:
                lowered = col.lower()
                if not any(pattern in lowered for pattern in lowered_patterns):
                    continue
            entry_cols.append(col)

        features.extend(entry_cols)

        for column in RISK_FEATURE_COLUMNS:
            if column in df.columns:
                features.append(column)

        # Categorical: side (one-hot encode)
        if "side" in df.columns:
            side_dummies = pd.get_dummies(df["side"], prefix="side", drop_first=False)
            df = pd.concat([df, side_dummies], axis=1)
            features.extend(side_dummies.columns.tolist())

        # Categorical: symbol (one-hot encode)
        if "symbol" in df.columns:
            symbol_dummies = pd.get_dummies(
                df["symbol"], prefix="symbol", drop_first=False
            )
            df = pd.concat([df, symbol_dummies], axis=1)
            features.extend(symbol_dummies.columns.tolist())

        # Temporal: Derived from entry_time
        if "entry_time" in df.columns:
            df["hour_of_day"] = pd.to_datetime(df["entry_time"]).dt.hour
            df["day_of_week"] = pd.to_datetime(df["entry_time"]).dt.dayofweek
            features.extend(["hour_of_day", "day_of_week"])

        # Return only extracted features
        return df[features].copy()

    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Align features with training feature names.

        Handles missing features (fill with 0) and extra features (drop).

        Args:
            X: DataFrame with extracted features

        Returns:
            DataFrame aligned with self.feature_names_
        """
        if self.feature_names_ is None:
            raise ValueError("Model not fitted")

        # Add missing features (fill with 0)
        for feature in self.feature_names_:
            if feature not in X.columns:
                X[feature] = 0

        # Keep only training features in same order
        return X[self.feature_names_]

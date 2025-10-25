"""ProfitabilityModel - Context-specific predictive models for signal filtering.

This module implements specialized profitability prediction models, one per timeframe/archetype
combination. Each model uses only entry-time features (no lookahead) to predict whether a trade
will be profitable, making them suitable for real-time signal filtering.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer


class ProfitabilityModel:
    """Context-specific binary classifier for profitability prediction.

    Each model specializes in a specific timeframe/archetype combination and uses only features
    known at entry time (no lookahead). This ensures the model can be used in real-time for
    signal filtering.

    Features used:
    - All `context_at_entry_*` columns (market indicators at entry)
    - `side` (long/short) - one-hot encoded
    - `symbol` (currency pair) - one-hot encoded
    - Temporal features from `entry_time` (hour, day_of_week, trading session)

    Target: Binary classification (profitable=1, unprofitable=0)
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
            n_estimators: Number of trees in RandomForestClassifier
            random_state: Random seed for reproducibility
        """
        self.timeframe = timeframe
        self.archetype = archetype
        self.n_estimators = n_estimators
        self.random_state = random_state

        # Model components (initialized during fit)
        self.model: RandomForestClassifier | None = None
        self.feature_names_: list[str] | None = None
        self.imputer: SimpleImputer | None = None

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
                f"Insufficient data: need 50+ trades for {self.timeframe}_{self.archetype}, got 0"
            )

        # Filter data by context
        df = trades_df[
            (trades_df["execution_timeframe"] == self.timeframe)
            & (trades_df["strategy_archetype"] == self.archetype)
        ].copy()

        # Validate minimum samples
        if len(df) < 50:
            raise ValueError(
                f"Insufficient data: need 50+ trades for {self.timeframe}_{self.archetype}, "
                f"got {len(df)}"
            )

        # Extract features (ONLY entry-time features - NO lookahead)
        X = self._extract_features(df)

        # Create target: binary classification (profitable=1, unprofitable=0)
        y = (df["pnl"] > 0).astype(int).values

        # Store feature names for later alignment
        self.feature_names_ = X.columns.tolist()

        # Initialize and fit imputer (handle missing values)
        self.imputer = SimpleImputer(strategy="mean")
        X_imputed = self.imputer.fit_transform(X)

        # Initialize and fit model
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,  # Use all cores
        )
        self.model.fit(X_imputed, y)

        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict profitability (binary: 0 or 1).

        Args:
            X: DataFrame with trade features (same structure as training data)

        Returns:
            Array of predictions (0=unprofitable, 1=profitable)

        Raises:
            ValueError: If model not fitted
        """
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract and align features
        X_features = self._extract_features(X)
        X_aligned = self._align_features(X_features)

        # Impute missing values
        X_imputed = self.imputer.transform(X_aligned)

        return self.model.predict(X_imputed)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict profitability probabilities.

        Args:
            X: DataFrame with trade features

        Returns:
            Array of shape (n_samples, 2) with probabilities for each class
            [:,0] = probability of unprofitable, [:,1] = probability of profitable

        Raises:
            ValueError: If model not fitted
        """
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract and align features
        X_features = self._extract_features(X)
        X_aligned = self._align_features(X_features)

        # Impute missing values
        X_imputed = self.imputer.transform(X_aligned)

        return self.model.predict_proba(X_imputed)

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
        features = []

        # 1. Pattern match: All context_at_entry_* columns
        entry_cols = [col for col in df.columns if col.startswith("context_at_entry_")]
        features.extend(entry_cols)

        # 2. Categorical: side (one-hot encode)
        if "side" in df.columns:
            side_dummies = pd.get_dummies(df["side"], prefix="side", drop_first=False)
            df = pd.concat([df, side_dummies], axis=1)
            features.extend(side_dummies.columns.tolist())

        # 3. Categorical: symbol (one-hot encode)
        if "symbol" in df.columns:
            symbol_dummies = pd.get_dummies(
                df["symbol"], prefix="symbol", drop_first=False
            )
            df = pd.concat([df, symbol_dummies], axis=1)
            features.extend(symbol_dummies.columns.tolist())

        # 4. Temporal: Derived from entry_time
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

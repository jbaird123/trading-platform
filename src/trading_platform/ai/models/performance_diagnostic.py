"""PerformanceDiagnosticModel - Context-specific regime analysis models.

This module implements specialized performance diagnostic models, one per
timeframe/archetype combination. Each model uses ALL available features
(including lookahead) to predict performance quintiles, making them suitable
for offline regime analysis and strategy improvement.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer


class PerformanceDiagnosticModel:
    """Context-specific quintile classifier for regime analysis.

    Each model specializes in a specific timeframe/archetype combination and
    uses ALL features including lookahead data. This is for offline analysis
    only - identifying which market regimes produce better/worse performance.

    Features used (ALL available data):
    - Entry features: All `context_at_entry_*` columns
    - Entry metadata: `side`, `symbol` (one-hot encoded), temporal from
      `entry_time`
    - Exit features: All `context_at_exit_*` columns (LOOKAHEAD)
    - Exit metadata: `exit_reason` (one-hot encoded, LOOKAHEAD)
    - Trade execution: `bars_held`, `mae_currency`, `mfe_currency`
      (LOOKAHEAD)
    - Post-trade analysis: All `post_exit_analysis_*` columns (LOOKAHEAD)
    - Cost features: `cost_breakdown_commission`, `cost_breakdown_slippage`,
      `cost_breakdown_spread`

    Target: Quintile classification based on r_multiple
            (0=worst 20%, 4=best 20%)
    """

    def __init__(
        self,
        timeframe: str,
        archetype: str,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        """Initialize PerformanceDiagnosticModel for specific context.

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

    def fit(self, trades_df: pd.DataFrame) -> "PerformanceDiagnosticModel":
        """Train model on historical trades.

        Args:
            trades_df: DataFrame with enriched trade data containing:
                - execution_timeframe, strategy_archetype (for filtering)
                - context_at_entry_* columns (entry features)
                - context_at_exit_* columns (exit features, lookahead)
                - side, symbol, entry_time (metadata)
                - exit_reason (lookahead)
                - bars_held, mae_currency, mfe_currency (lookahead)
                - post_exit_analysis_* columns (lookahead)
                - cost_breakdown_* columns
                - r_multiple (target)

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

        # Remove rows with missing r_multiple (can't classify without target)
        df_clean = df.dropna(subset=["r_multiple"]).copy()

        if len(df_clean) < 50:
            raise ValueError(
                f"Insufficient data after removing missing r_multiple: "
                f"need 50+ trades for {self.timeframe}_{self.archetype}, "
                f"got {len(df_clean)}"
            )

        # Extract features (ALL features including lookahead)
        X = self._extract_features(df_clean)

        # Create target: quintile classification based on r_multiple
        # Convert to numpy array explicitly for type safety
        r_multiple_values: np.ndarray = np.asarray(df_clean["r_multiple"].values)
        y = self._create_quintile_target(r_multiple_values)

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
        """Predict performance quintile (0-4).

        Args:
            X: DataFrame with trade features (same structure as training data)

        Returns:
            Array of predictions (0=worst, 4=best)

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

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict quintile probabilities.

        Args:
            X: DataFrame with trade features

        Returns:
            Array of shape (n_samples, 5) with probabilities for each quintile
            [:,0] = probability of quintile 0 (worst)
            ...
            [:,4] = probability of quintile 4 (best)

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
        probabilities: np.ndarray = self.model.predict_proba(X_imputed)
        return probabilities

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
    def load(cls, path: Path) -> "PerformanceDiagnosticModel":
        """Load model from disk.

        Args:
            path: Path to saved model (.pkl file)

        Returns:
            Loaded PerformanceDiagnosticModel instance
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
        """Extract ALL features from DataFrame (including lookahead).

        Args:
            df: Raw trades DataFrame

        Returns:
            DataFrame with all available features
        """
        features = []

        # 1. Pattern match: All context_at_entry_* columns
        entry_cols = [col for col in df.columns if col.startswith("context_at_entry_")]
        features.extend(entry_cols)

        # 2. Pattern match: All context_at_exit_* columns (LOOKAHEAD)
        exit_cols = [col for col in df.columns if col.startswith("context_at_exit_")]
        features.extend(exit_cols)

        # 3. Pattern match: All post_exit_analysis_* columns (LOOKAHEAD)
        # NOTE: Exclude the nested post_exit_analysis_simulated_holds column
        # (it should have been unpacked by the registry before training)
        post_exit_cols = [
            col
            for col in df.columns
            if col.startswith("post_exit_analysis_")
            and col != "post_exit_analysis_simulated_holds"
        ]
        features.extend(post_exit_cols)

        # 3a. Pattern match: All sim_hold_* numeric columns (LOOKAHEAD)
        # These are the unpacked simulated hold features (PnL, etc.)
        sim_hold_numeric_cols = [
            col
            for col in df.columns
            if col.startswith("sim_hold_") and not col.endswith("_exit_reason")
        ]
        features.extend(sim_hold_numeric_cols)

        # 4. Categorical: side (one-hot encode)
        if "side" in df.columns:
            side_dummies = pd.get_dummies(df["side"], prefix="side", drop_first=False)
            df = pd.concat([df, side_dummies], axis=1)
            features.extend(side_dummies.columns.tolist())

        # 5. Categorical: symbol (one-hot encode)
        if "symbol" in df.columns:
            symbol_dummies = pd.get_dummies(
                df["symbol"], prefix="symbol", drop_first=False
            )
            df = pd.concat([df, symbol_dummies], axis=1)
            features.extend(symbol_dummies.columns.tolist())

        # 6. Categorical: exit_reason (one-hot encode, LOOKAHEAD)
        if "exit_reason" in df.columns:
            exit_reason_dummies = pd.get_dummies(
                df["exit_reason"], prefix="exit_reason", drop_first=False
            )
            df = pd.concat([df, exit_reason_dummies], axis=1)
            features.extend(exit_reason_dummies.columns.tolist())

        # 6a. Categorical: sim_hold_*_exit_reason columns (one-hot encode, LOOKAHEAD)
        # Encode all categorical exit_reason columns from simulated holds
        sim_hold_exit_reason_cols = [
            col
            for col in df.columns
            if col.endswith("_exit_reason") and col.startswith("sim_hold_")
        ]
        for col in sim_hold_exit_reason_cols:
            col_dummies = pd.get_dummies(df[col], prefix=col, drop_first=False)
            df = pd.concat([df, col_dummies], axis=1)
            features.extend(col_dummies.columns.tolist())

        # 7. Temporal: Derived from entry_time
        if "entry_time" in df.columns:
            df["hour_of_day"] = pd.to_datetime(df["entry_time"]).dt.hour
            df["day_of_week"] = pd.to_datetime(df["entry_time"]).dt.dayofweek
            features.extend(["hour_of_day", "day_of_week"])

        # 8. Trade execution features (LOOKAHEAD)
        execution_features = ["bars_held", "mae_currency", "mfe_currency"]
        for feat in execution_features:
            if feat in df.columns:
                features.append(feat)

        # 9. Cost features
        cost_features = [
            "cost_breakdown_commission",
            "cost_breakdown_slippage",
            "cost_breakdown_spread",
        ]
        for feat in cost_features:
            if feat in df.columns:
                features.append(feat)

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

    def _create_quintile_target(self, r_multiples: np.ndarray) -> np.ndarray:
        """Create quintile labels from r_multiple values.

        Args:
            r_multiples: Array of r_multiple values

        Returns:
            Array of quintile labels (0=worst 20%, 4=best 20%)
        """
        # Use qcut to create 5 equal-sized bins
        quintiles = pd.qcut(
            r_multiples,
            q=5,
            labels=[0, 1, 2, 3, 4],
            duplicates="drop",  # Handle case where we have duplicate bin edges
        )

        # Convert to numpy array (qcut may return Series or ndarray)
        if isinstance(quintiles, pd.Series):
            result: np.ndarray = quintiles.astype(int).values
            return result
        else:
            result_arr: np.ndarray = np.asarray(quintiles.astype(int))
            return result_arr

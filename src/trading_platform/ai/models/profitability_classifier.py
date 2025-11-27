"""Gradient boosting classifier for profitability filtering."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import GradientBoostingClassifier

from ._timeframe_utils import drop_lower_timeframe_global_features
from .feature_groups import (
    ENGINEERED_GROUP_PATTERNS,
    RISK_FEATURE_COLUMNS,
    add_normalized_risk_features,
    collect_group_patterns,
)
from .profitability import SELECTED_FEATURE_GROUPS


class ProfitabilityClassifierModel:
    """Timeframe/archetype specific profitability classifier."""

    def __init__(
        self,
        timeframe: str,
        archetype: str,
        random_state: int = 42,
    ) -> None:
        self.timeframe = timeframe
        self.archetype = archetype
        self.random_state = random_state

        self.model: GradientBoostingClassifier | None = None
        self.feature_names_: list[str] | None = None
        self.training_start_date_: pd.Timestamp | None = None
        self.training_end_date_: pd.Timestamp | None = None

    # ---------------------------------------------------------------------
    # Training helpers
    # ---------------------------------------------------------------------

    def fit(self, trades_df: pd.DataFrame) -> ProfitabilityClassifierModel:
        """Train classifier on trades with r_multiple labels."""

        df = trades_df[
            (trades_df["execution_timeframe"] == self.timeframe)
            & (trades_df["strategy_archetype"] == self.archetype)
        ].copy()

        if len(df) < 50:
            raise ValueError(
                "Insufficient data for classifier "
                f"{self.timeframe}_{self.archetype}: {len(df)} trades found "
                "(need >= 50)."
            )

        if "r_multiple" not in df.columns:
            raise ValueError(
                "Missing r_multiple column for classifier "
                f"{self.timeframe}_{self.archetype}"
            )

        if df["r_multiple"].isnull().any():
            missing = int(df["r_multiple"].isnull().sum())
            raise ValueError(
                f"Classifier {self.timeframe}_{self.archetype} cannot train with "
                f"{missing} missing r_multiple values."
            )

        entry_times = pd.to_datetime(df["entry_time"], utc=True)
        self.training_start_date_ = entry_times.min()
        self.training_end_date_ = entry_times.max()

        df = drop_lower_timeframe_global_features(df, self.timeframe)

        X = self._extract_features(df)
        y = (df["r_multiple"] > 0.0).astype(int).to_numpy()

        pos = y.sum()
        neg = len(y) - pos
        weight_pos = len(y) / (2.0 * pos) if pos > 0 else 1.0
        weight_neg = len(y) / (2.0 * neg) if neg > 0 else 1.0
        sample_weight = np.where(y == 1, weight_pos, weight_neg)

        model = GradientBoostingClassifier(random_state=self.random_state)
        model.fit(X, y, sample_weight=sample_weight)

        self.model = model
        self.feature_names_ = X.columns.tolist()
        return self

    def predict_proba(self, X: pd.DataFrame) -> NDArray[np.float64]:
        if self.model is None:
            raise ValueError("Classifier not fitted")
        features = self._extract_features(X)
        self._assert_required_features(features)
        aligned = self._align_features(features)
        aligned = aligned.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        probabilities = cast(NDArray[np.float64], self.model.predict_proba(aligned))
        class_probs: NDArray[np.float64] = probabilities[:, 1]
        return class_probs

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X) >= 0.5).astype(int)

    # ---------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------

    def save(self, path: Path) -> None:
        payload = {
            "timeframe": self.timeframe,
            "archetype": self.archetype,
            "random_state": self.random_state,
            "model": self.model,
            "feature_names": self.feature_names_,
            "training_start": self.training_start_date_,
            "training_end": self.training_end_date_,
        }
        joblib.dump(payload, path)

    @classmethod
    def load(cls, path: Path) -> ProfitabilityClassifierModel:
        payload = joblib.load(path)
        instance = cls(
            timeframe=payload["timeframe"],
            archetype=payload["archetype"],
            random_state=payload["random_state"],
        )
        instance.model = payload["model"]
        instance.feature_names_ = payload["feature_names"]
        instance.training_start_date_ = payload["training_start"]
        instance.training_end_date_ = payload["training_end"]
        return instance

    # ---------------------------------------------------------------------
    # Feature engineering helpers (mirrors ProfitabilityModel)
    # ---------------------------------------------------------------------

    def _extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
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

        if "side" in df.columns:
            side_dummies = pd.get_dummies(df["side"], prefix="side", drop_first=False)
            df = pd.concat([df, side_dummies], axis=1)
            features.extend(side_dummies.columns.tolist())

        if "symbol" in df.columns:
            symbol_dummies = pd.get_dummies(
                df["symbol"], prefix="symbol", drop_first=False
            )
            df = pd.concat([df, symbol_dummies], axis=1)
            features.extend(symbol_dummies.columns.tolist())

        if "entry_time" in df.columns:
            df["hour_of_day"] = pd.to_datetime(df["entry_time"]).dt.hour
            df["day_of_week"] = pd.to_datetime(df["entry_time"]).dt.dayofweek
            features.extend(["hour_of_day", "day_of_week"])

        feature_df = df[features].copy()
        bool_cols = feature_df.select_dtypes(include=["bool"]).columns
        if len(bool_cols) > 0:
            feature_df[bool_cols] = feature_df[bool_cols].astype(int)
        numeric_df = feature_df.select_dtypes(include=["number"])
        return numeric_df

    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        names = self._required_feature_names()
        if not names:
            raise ValueError("Classifier not fitted")

        for feature in names:
            if feature not in X.columns:
                X[feature] = 0

        return X[names]

    def _assert_required_features(self, X: pd.DataFrame) -> None:
        names = self._required_feature_names()
        if not names:
            return
        optional_prefixes = ("side_", "symbol_")
        optional_columns = {"hour_of_day", "day_of_week"}
        missing = []
        for name in names:
            if name in X.columns:
                continue
            if any(name.startswith(prefix) for prefix in optional_prefixes):
                continue
            if name in optional_columns:
                continue
            missing.append(name)
        if missing:
            raise ValueError(
                "Missing required features: "
                f"{missing}. Ensure enrichment pipeline supplies these columns."
            )

    def _required_feature_names(self) -> list[str]:
        if self.model is not None and hasattr(self.model, "feature_names_in_"):
            return list(self.model.feature_names_in_)
        return self.feature_names_ or []

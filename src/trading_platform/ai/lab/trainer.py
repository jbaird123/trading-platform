from typing import Any, List, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def train_profitability_model(brief: dict) -> Tuple[Any, List[str]]:
    """
    Trains a RandomForestClassifier to predict trade profitability.
    Features are extracted from entry_context for each trade.
    Target is binary: 1 if pnl > 0, else 0.
    Returns the trained model and the feature list.
    """
    trades = brief.get("trades", [])
    if not trades:
        raise ValueError("No trades found in brief.")

    # Extract features and target
    feature_names_set = set()
    for trade in trades:
        feature_names_set.update(trade.get("entry_context", {}).keys())
    feature_names: List[str] = sorted(feature_names_set)

    X_list: List[List[Any]] = []
    y_list: List[int] = []
    for trade in trades:
        context = trade.get("entry_context", {})
        features = [context.get(f, np.nan) for f in feature_names]
        X_list.append(features)
        y_list.append(1 if trade.get("pnl", 0) > 0 else 0)

    X: np.ndarray = np.array(X_list)
    y: np.ndarray = np.array(y_list)

    # Handle missing values (simple imputation)
    from sklearn.impute import SimpleImputer

    imputer = SimpleImputer(strategy="mean")
    X = imputer.fit_transform(X)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    return model, feature_names


def save_model(model: Any, path: str):
    joblib.dump(model, path)

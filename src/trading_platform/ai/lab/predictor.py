from typing import Any, Dict, List
import shap
import numpy as np

def get_trade_insights(model: Any, trade: dict, features: List[str]) -> Dict:
    """
    Predicts profitability for a single trade and returns SHAP feature importances.
    """
    context = trade.get("entry_context", {})
    X = np.array([[context.get(f, np.nan) for f in features]])

    # Predict profitability
    pred = model.predict(X)[0]
    pred_proba = model.predict_proba(X)[0][1] if hasattr(model, "predict_proba") else None

    # SHAP values
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    # For binary classification, shap_values is a list
    if isinstance(shap_values, list):
        shap_vals = shap_values[1][0]  # Class 1 (profitable)
    else:
        shap_vals = shap_values[0]

    feature_importances = dict(zip(features, shap_vals))

    return {
        "predicted_profitable": bool(pred),
        "predicted_probability": float(pred_proba) if pred_proba is not None else None,
        "feature_importances": feature_importances
    }

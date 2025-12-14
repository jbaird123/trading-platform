#!/usr/bin/env python3
"""
Phase 1.1b: Entry-Time Feature Importance Analysis

This script focuses on features available at entry time (context_at_entry)
that can be used for live trading decisions.

Output:
  - artifacts/entry_features_importance.csv
  - artifacts/entry_features_top_by_model.csv
"""

from pathlib import Path

import joblib
import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = Path("data/dvc/ml/models/diagnostic")


def main():
    print("=" * 80)
    print("PHASE 1.1b: ENTRY-TIME FEATURE IMPORTANCE")
    print("=" * 80)
    print("\nFocusing only on context_at_entry features (usable for live trading)")

    # Find all diagnostic models
    model_files = list(MODELS_DIR.glob("*.pkl"))
    print(f"\nFound {len(model_files)} diagnostic models")

    results = []

    for model_path in model_files:
        try:
            payload = joblib.load(model_path)
            model = payload.get("model")
            features = payload.get("feature_names", [])

            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
                for feat, imp in zip(features, importances):
                    # Only include context_at_entry features
                    if "context_at_entry" in feat:
                        # Clean up feature name for readability
                        clean_name = feat.replace("context_at_entry_", "")
                        results.append(
                            {
                                "model": model_path.stem,
                                "feature": feat,
                                "feature_short": clean_name,
                                "importance": imp,
                            }
                        )

        except Exception as e:
            print(f"  ERROR processing {model_path.stem}: {e}")

    if not results:
        print("\nERROR: No entry features extracted!")
        return

    # Create DataFrame
    df = pd.DataFrame(results)
    df = df.sort_values(["model", "importance"], ascending=[True, False])
    df.to_csv(OUTPUT_DIR / "entry_features_importance.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'entry_features_importance.csv'}")

    # Top 15 entry features per model
    print("\n" + "=" * 80)
    print("TOP 15 ENTRY-TIME FEATURES PER MODEL")
    print("=" * 80)

    top_per_model = []
    for model_name in df["model"].unique():
        model_df = df[df["model"] == model_name]
        top = model_df.head(15)

        print(f"\n--- {model_name} ---")
        for i, (_, row) in enumerate(top.iterrows(), 1):
            print(f"  {i:2d}. {row['importance']:.4f}  {row['feature_short']}")
            top_per_model.append(
                {
                    "model": model_name,
                    "rank": i,
                    "feature": row["feature"],
                    "feature_short": row["feature_short"],
                    "importance": row["importance"],
                }
            )

    top_df = pd.DataFrame(top_per_model)
    top_df.to_csv(OUTPUT_DIR / "entry_features_top_by_model.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'entry_features_top_by_model.csv'}")

    # Cross-model analysis
    print("\n" + "=" * 80)
    print("ENTRY FEATURES APPEARING IN TOP 15 ACROSS MULTIPLE MODELS")
    print("=" * 80)

    feature_counts = (
        top_df.groupby("feature_short")
        .agg({"model": "count", "importance": "mean", "rank": "mean"})
        .reset_index()
    )
    feature_counts.columns = ["feature", "model_count", "avg_importance", "avg_rank"]
    feature_counts = feature_counts.sort_values(
        ["model_count", "avg_importance"], ascending=[False, False]
    )

    print("\nFeatures appearing in top 15 of 2+ models:")
    multi = feature_counts[feature_counts["model_count"] >= 2]
    for _, row in multi.iterrows():
        print(
            f"  {row['model_count']:2d}/10 models (avg rank {row['avg_rank']:.1f}): {row['feature']}"
        )

    # Group by feature category
    print("\n" + "=" * 80)
    print("FEATURE CATEGORIES IN TOP 15")
    print("=" * 80)

    # Extract timeframe and feature type
    def categorize_feature(feat):
        parts = feat.split("_")
        # Find timeframe
        timeframes = ["5min", "15min", "1h", "4h", "1d", "1w"]
        tf = "unknown"
        for t in timeframes:
            if t in feat.lower():
                tf = t
                break

        # Find category
        if "atr" in feat.lower():
            cat = "volatility_atr"
        elif "bb_width" in feat.lower():
            cat = "volatility_bb"
        elif "ema" in feat.lower():
            cat = "trend_ema"
        elif "rsi" in feat.lower():
            cat = "momentum_rsi"
        elif "trend_alignment" in feat.lower():
            cat = "trend_alignment"
        elif "roc" in feat.lower():
            cat = "momentum_roc"
        elif "hhv" in feat.lower() or "llv" in feat.lower():
            cat = "range_hhv_llv"
        elif "risk" in feat.lower():
            cat = "risk"
        elif "day_of_week" in feat.lower():
            cat = "calendar"
        elif "volume" in feat.lower():
            cat = "volume"
        else:
            cat = "other"

        return tf, cat

    top_df["timeframe"], top_df["category"] = zip(
        *top_df["feature_short"].apply(categorize_feature)
    )

    # Count by category
    cat_counts = top_df.groupby("category").size().sort_values(ascending=False)
    print("\nFeature categories in top 15 (across all models):")
    for cat, count in cat_counts.items():
        print(f"  {count:3d} features: {cat}")

    # Count by timeframe
    tf_counts = top_df.groupby("timeframe").size().sort_values(ascending=False)
    print("\nTimeframes in top 15:")
    for tf, count in tf_counts.items():
        print(f"  {count:3d} features: {tf}")

    # Risk features specifically
    print("\n" + "=" * 80)
    print("RISK-RELATED FEATURES")
    print("=" * 80)

    risk_features = df[df["feature_short"].str.contains("risk", case=False)]
    if len(risk_features) > 0:
        risk_summary = (
            risk_features.groupby("feature_short")
            .agg({"model": "count", "importance": ["mean", "max"]})
            .reset_index()
        )
        risk_summary.columns = [
            "feature",
            "model_count",
            "avg_importance",
            "max_importance",
        ]
        risk_summary = risk_summary.sort_values("avg_importance", ascending=False)

        print("\nRisk features across models:")
        for _, row in risk_summary.iterrows():
            print(
                f"  {row['model_count']:2d}/10 models: {row['feature']} (avg: {row['avg_importance']:.4f}, max: {row['max_importance']:.4f})"
            )


if __name__ == "__main__":
    main()

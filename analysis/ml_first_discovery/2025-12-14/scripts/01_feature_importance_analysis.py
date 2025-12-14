#!/usr/bin/env python3
"""
Phase 1.1: Feature Importance Analysis

This script extracts feature importances from diagnostic models
to understand what conditions predict winning trades.

Output:
  - artifacts/feature_importances.csv
  - artifacts/feature_importances_entry_only.csv
  - artifacts/top_features_summary.csv
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
    print("PHASE 1.1: FEATURE IMPORTANCE ANALYSIS")
    print("=" * 80)

    # Find all diagnostic models
    model_files = list(MODELS_DIR.glob("*.pkl"))
    print(f"\nFound {len(model_files)} diagnostic models")

    results = []

    for model_path in model_files:
        print(f"\nProcessing: {model_path.stem}")

        try:
            payload = joblib.load(model_path)
            model = payload.get("model")
            features = payload.get("feature_names", [])

            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
                for feat, imp in zip(features, importances):
                    results.append(
                        {"model": model_path.stem, "feature": feat, "importance": imp}
                    )
                print(f"  Extracted {len(features)} feature importances")
            else:
                print("  WARNING: Model does not have feature_importances_")

        except Exception as e:
            print(f"  ERROR: {e}")

    if not results:
        print("\nERROR: No feature importances extracted!")
        return

    # Create DataFrame and save full results
    df = pd.DataFrame(results)
    df = df.sort_values(["model", "importance"], ascending=[True, False])
    df.to_csv(OUTPUT_DIR / "feature_importances.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'feature_importances.csv'}")

    # Filter to entry-only features (exclude exit context and post-exit)
    entry_only = df[
        ~df["feature"].str.contains("context_at_exit|post_exit", case=False, na=False)
    ].copy()
    entry_only.to_csv(OUTPUT_DIR / "feature_importances_entry_only.csv", index=False)
    print(f"Saved: {OUTPUT_DIR / 'feature_importances_entry_only.csv'}")

    # Summary: Top features across models
    print("\n" + "=" * 80)
    print("TOP 10 FEATURES PER MODEL")
    print("=" * 80)

    for model_name in df["model"].unique():
        print(f"\n--- {model_name} ---")
        top = df[df["model"] == model_name].head(10)
        for _, row in top.iterrows():
            print(f"  {row['importance']:.4f}  {row['feature']}")

    # Cross-model analysis: which features appear most frequently in top 10?
    print("\n" + "=" * 80)
    print("FEATURES APPEARING IN TOP 10 ACROSS MULTIPLE MODELS")
    print("=" * 80)

    top_features_per_model = []
    for model_name in df["model"].unique():
        top = df[df["model"] == model_name].head(10)["feature"].tolist()
        for feat in top:
            top_features_per_model.append({"model": model_name, "feature": feat})

    top_df = pd.DataFrame(top_features_per_model)
    feature_counts = top_df.groupby("feature").size().reset_index(name="model_count")
    feature_counts = feature_counts.sort_values("model_count", ascending=False)

    # Add average importance
    avg_importance = df.groupby("feature")["importance"].mean().reset_index()
    avg_importance.columns = ["feature", "avg_importance"]

    summary = feature_counts.merge(avg_importance, on="feature")
    summary = summary.sort_values(
        ["model_count", "avg_importance"], ascending=[False, False]
    )
    summary.to_csv(OUTPUT_DIR / "top_features_summary.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'top_features_summary.csv'}")

    print("\nFeatures in top 10 of multiple models:")
    multi_model = summary[summary["model_count"] > 1]
    for _, row in multi_model.iterrows():
        print(
            f"  {row['model_count']}/{len(df['model'].unique())} models: {row['feature']} (avg imp: {row['avg_importance']:.4f})"
        )

    # Entry-only cross-model analysis
    print("\n" + "=" * 80)
    print("ENTRY-ONLY FEATURES IN TOP 10 ACROSS MULTIPLE MODELS")
    print("=" * 80)

    top_entry_per_model = []
    for model_name in entry_only["model"].unique():
        top = entry_only[entry_only["model"] == model_name].head(10)["feature"].tolist()
        for feat in top:
            top_entry_per_model.append({"model": model_name, "feature": feat})

    if top_entry_per_model:
        top_entry_df = pd.DataFrame(top_entry_per_model)
        entry_counts = (
            top_entry_df.groupby("feature").size().reset_index(name="model_count")
        )
        entry_counts = entry_counts.sort_values("model_count", ascending=False)

        print("\nEntry-time features appearing in multiple models:")
        multi_entry = entry_counts[entry_counts["model_count"] > 1]
        for _, row in multi_entry.head(15).iterrows():
            print(f"  {row['model_count']} models: {row['feature']}")


if __name__ == "__main__":
    main()

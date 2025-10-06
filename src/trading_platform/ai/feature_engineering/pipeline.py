"""
This module defines the feature engineering pipeline for the AI Lab.
It delegates to the centralized feature computation system.
"""

from typing import Any, Dict, List

import pandas as pd

from trading_platform.strategy.features import compute_features


class FeatureEngineeringPipeline:
    """
    A pipeline for generating technical analysis features from market data.
    """

    def __init__(self, df: pd.DataFrame):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input 'df' must be a pandas DataFrame.")
        self.df = df.copy()

    def add_feature(self, feature_config: Dict[str, Any]):
        """
        Adds a single feature to the DataFrame based on a configuration.

        Args:
            feature_config: A dictionary defining the feature, e.g.,
                            {'kind': 'sma', 'params': {'length': 50}}
        """
        kind = feature_config.get("kind")
        if not kind:
            raise ValueError("Feature config must include a 'kind'.")

        params = feature_config.get("params", {})
        length = params.get("length", 14)

        # Convert to the format expected by compute_features
        spec = {
            "name": f"{kind.lower()}_{length}",
            "type": kind.upper(),
            "params": params,
            "source": "close",
        }

        # Use centralized feature computation
        self.df = compute_features(self.df, [spec])

    def run(self, feature_configs: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Runs the feature engineering pipeline.

        Args:
            feature_configs: A list of feature configuration dictionaries.

        Returns:
            A new DataFrame with the added feature columns.
        """
        print(
            f"Running feature engineering for {len(feature_configs)} "
            f"features..."
        )

        # Convert all configs to specs format
        specs = []
        for config in feature_configs:
            kind = config.get("kind")
            if not kind:
                raise ValueError("Feature config must include a 'kind'.")
            params = config.get("params", {})
            length = params.get("length", 14)

            spec = {
                "name": f"{kind.lower()}_{length}",
                "type": kind.upper(),
                "params": params,
                "source": "close",
            }
            specs.append(spec)

        # Use centralized feature computation
        self.df = compute_features(self.df, specs)

        # Drop rows with NaN values that are created by indicators
        self.df.dropna(inplace=True)

        print("Feature engineering complete.")
        return self.df


# Example usage
if __name__ == "__main__":
    # Sample DataFrame (e.g., from AIDataConnector)
    data = {
        "timestamp": pd.to_datetime(
            [
                "2023-01-01",
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
                "2023-01-07",
                "2023-01-08",
            ]
        ),
        "open": [1.0, 1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10],
        "high": [1.1, 1.15, 1.12, 1.10, 1.18, 1.17, 1.16, 1.12],
        "low": [0.95, 1.0, 1.07, 1.05, 1.09, 1.12, 1.10, 1.08],
        "close": [1.05, 1.1, 1.08, 1.12, 1.15, 1.13, 1.10, 1.09],
        "volume": [100, 110, 105, 120, 115, 130, 125, 110],
    }
    sample_df = pd.DataFrame(data).set_index("timestamp")

    # Define features to be generated
    features_to_add = [
        {"kind": "sma", "params": {"length": 2}},
        {"kind": "rsi", "params": {"length": 2}},
    ]

    pipeline = FeatureEngineeringPipeline(sample_df)
    featured_df = pipeline.run(features_to_add)

    print("\nDataFrame with new features:")
    print(featured_df)

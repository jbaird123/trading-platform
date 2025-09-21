"""
This module defines the feature engineering pipeline for the AI Lab.
It is a placeholder and uses the `ta` library, consistent with the rest of the platform.
"""

from typing import Any, Dict, List

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator


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
                            {'kind': 'sma', 'length': 50}
        """
        kind = feature_config.get("kind")
        if not kind:
            raise ValueError("Feature config must include a 'kind'.")

        # This is a simplified mapping. A real implementation would be more robust
        # and likely driven by the central indicators_registry.py.
        if kind == "sma":
            length = feature_config.get("length", 14)
            indicator = SMAIndicator(close=self.df["close"], window=length)
            self.df[f"sma_{length}"] = indicator.sma_indicator()
        elif kind == "rsi":
            length = feature_config.get("length", 14)
            indicator = RSIIndicator(close=self.df["close"], window=length)
            self.df[f"rsi_{length}"] = indicator.rsi()
        else:
            # For now, we only support sma and rsi in this placeholder
            raise NotImplementedError(f"Feature '{kind}' is not supported yet.")

    def run(self, feature_configs: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Runs the feature engineering pipeline.

        Args:
            feature_configs: A list of feature configuration dictionaries.

        Returns:
            A new DataFrame with the added feature columns.
        """
        print(
            f"Running feature engineering pipeline for {len(feature_configs)} features..."
        )
        for config in feature_configs:
            self.add_feature(config)

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
        {"kind": "sma", "length": 2},
        {"kind": "rsi", "length": 2},
    ]

    pipeline = FeatureEngineeringPipeline(sample_df)
    featured_df = pipeline.run(features_to_add)

    print("\nDataFrame with new features:")
    print(featured_df)

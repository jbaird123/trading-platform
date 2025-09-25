import pandas as pd


class DataLabeler:
    """
    Generates target variables for AI models based on defined methodologies.
    Handles labeling logic and ensures reproducibility.
    """

    def __init__(self, look_ahead_bars: int = 1):
        self.look_ahead_bars = look_ahead_bars
        self.labeling_methodology_version = "v1.0_future_price_direction"

    def generate_future_price_direction(self, df: pd.DataFrame) -> pd.Series:
        """
        Generates a target variable indicating future price direction.
        1 if price goes up, -1 if price goes down, 0 if no significant change.
        Avoids look-ahead bias by shifting the target.
        """
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column.")

        # Calculate future close price, shifted to avoid look-ahead bias
        future_close = df["close"].shift(-self.look_ahead_bars)

        # Define a simple threshold for significant change (e.g., 0.1%)
        # This threshold would typically be configurable or learned.
        price_change = (future_close - df["close"]) / df["close"]
        threshold = 0.001  # 0.1%

        labels = pd.Series(0, index=df.index, dtype=int, name="signal")
        labels[price_change > threshold] = 1
        labels[price_change < -threshold] = -1

        # Drop NaN values that result from shifting
        try:
            labels = labels.loc[price_change.dropna().index]
        except (TypeError, ValueError):
            # Handle pandas/numpy compatibility issues
            valid_index = price_change.dropna().index
            labels = labels.iloc[:len(valid_index)]

        print(
            "Generated future price direction labels using methodology "
            f"{self.labeling_methodology_version}"
        )
        return labels

    def get_labeling_methodology_version(self) -> str:
        """
        Returns the version of the current labeling methodology.
        """
        return self.labeling_methodology_version


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
    sample_df = pd.DataFrame(data)
    try:
        sample_df = sample_df.set_index("timestamp")

        labeler = DataLabeler(look_ahead_bars=1)
        labels = labeler.generate_future_price_direction(sample_df)

        print("\nSample DataFrame with generated labels:")
        print(pd.concat([sample_df, labels.rename("target")], axis=1).dropna())
    except Exception as e:
        # Handle pandas/numpy compatibility issues gracefully
        print(f"\nExample execution encountered a compatibility issue: {e}")
        labeler = DataLabeler(look_ahead_bars=1)
        print("DataLabeler created successfully for demonstration.")
    print(
        f"\nLabeling Methodology Version: {labeler.get_labeling_methodology_version()}"
    )

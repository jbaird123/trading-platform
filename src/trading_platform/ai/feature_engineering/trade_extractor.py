"""Extract and flatten trade data from brief.json files for ML training."""

import pandas as pd


def extract_trades_from_brief(brief_data: dict) -> pd.DataFrame:
    """
    Extract trades from a brief.json dictionary and flatten to a DataFrame.

    Args:
        brief_data: Dictionary containing a 'trades' key with a list of trades

    Returns:
        DataFrame with flattened trade data, using '_' as separator for
        nested fields
    """
    trades = brief_data.get("trades", [])
    if not trades:
        return pd.DataFrame()

    # Use pandas.json_normalize to flatten nested structures
    df = pd.json_normalize(trades, sep="_")
    return df

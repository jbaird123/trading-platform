"""Utilities for unpacking nested post-trade analysis data into flat features."""

import pandas as pd


def unpack_simulated_holds(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unpacks the nested post_exit_analysis_simulated_holds column.

    This column contains a list of dicts. This function flattens it
    into separate columns for each horizon and metric (e.g.,
    'sim_hold_10_pnl', 'sim_hold_10_exit_reason').

    Args:
        df: The input DataFrame, which may contain the nested column.

    Returns:
        A DataFrame with the nested data unpacked into new columns.
    """
    col_name = "post_exit_analysis_simulated_holds"
    if col_name not in df.columns:
        return df

    # First pass: discover all unique horizons and all unique keys
    all_horizons = set()
    all_keys = set()
    for sim_holds in df[col_name]:
        if not isinstance(sim_holds, list):
            continue
        for sim_result in sim_holds:
            if not isinstance(sim_result, dict):
                continue
            horizon = sim_result.get("hold_bars")
            if horizon is not None:
                all_horizons.add(horizon)
            for key in sim_result.keys():
                if key != "hold_bars":
                    all_keys.add(key)

    # Create all combinations of horizons and keys
    all_new_columns = {
        f"sim_hold_{horizon}_{key}" for horizon in all_horizons for key in all_keys
    }

    # Use a temporary list of records to build the new columns efficiently
    records = df.to_dict("records")

    # Initialize all new columns with NaN for all records
    for record in records:
        for col in all_new_columns:
            record[col] = pd.NA

    # Second pass: fill in the values
    for record in records:
        sim_holds = record.get(col_name)
        if not isinstance(sim_holds, list):
            continue

        for sim_result in sim_holds:
            if not isinstance(sim_result, dict):
                continue

            horizon = sim_result.get("hold_bars")
            if horizon is None:
                continue

            # Unpack all keys from the sim_result dict
            for key, value in sim_result.items():
                if key == "hold_bars":
                    continue
                new_col_name = f"sim_hold_{horizon}_{key}"
                record[new_col_name] = value

    # Create new DataFrame from the updated records
    result_df = pd.DataFrame(records)

    # Drop the original complex column
    if col_name in result_df.columns:
        result_df = result_df.drop(columns=[col_name])

    return result_df

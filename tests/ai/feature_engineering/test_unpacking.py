import pandas as pd
from trading_platform.ai.feature_engineering.unpacking import unpack_simulated_holds


class TestUnpackSimulatedHolds:
    def test_unpack_with_valid_data(self):
        """Verify that valid nested data is flattened correctly."""
        data = [
            {
                "id": 1,
                "post_exit_analysis_simulated_holds": [
                    {"hold_bars": 10, "pnl": 50.0, "exit_reason": "horizon_reached"},
                    {"hold_bars": 20, "pnl": -25.0, "exit_reason": "stop_loss_hit"},
                ],
            }
        ]
        df = pd.DataFrame(data)
        result_df = unpack_simulated_holds(df)
        assert "sim_hold_10_pnl" in result_df.columns
        assert "sim_hold_10_exit_reason" in result_df.columns
        assert "sim_hold_20_pnl" in result_df.columns
        assert "sim_hold_20_exit_reason" in result_df.columns
        assert result_df.loc[0, "sim_hold_10_pnl"] == 50.0
        assert result_df.loc[0, "sim_hold_20_exit_reason"] == "stop_loss_hit"
        assert "post_exit_analysis_simulated_holds" not in result_df.columns

    def test_unpack_with_missing_or_null_data(self):
        """Verify that it handles rows with missing or null data gracefully."""
        data = [
            {"id": 1, "post_exit_analysis_simulated_holds": None},
            {"id": 2, "post_exit_analysis_simulated_holds": []},
        ]
        df = pd.DataFrame(data)
        result_df = unpack_simulated_holds(df)
        assert (
            "sim_hold_10_pnl" not in result_df.columns
        )  # No columns should be created
        assert len(result_df) == 2

    def test_unpack_with_partially_missing_keys(self):
        """Verify it handles dicts with some keys missing."""
        data = [
            {
                "id": 1,
                "post_exit_analysis_simulated_holds": [
                    {"hold_bars": 10, "pnl": 50.0},  # Missing exit_reason
                    {"hold_bars": 20, "exit_reason": "stop_loss_hit"},  # Missing pnl
                ],
            }
        ]
        df = pd.DataFrame(data)
        result_df = unpack_simulated_holds(df)
        assert pd.isna(result_df.loc[0, "sim_hold_10_exit_reason"])
        assert pd.isna(result_df.loc[0, "sim_hold_20_pnl"])

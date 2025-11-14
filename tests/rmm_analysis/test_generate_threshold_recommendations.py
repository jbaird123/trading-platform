"""Smoke tests for generate_threshold_recommendations helper."""

from __future__ import annotations

import pandas as pd
from trading_platform.rmm_analysis import generate_threshold_recommendations as gen
from trading_platform.rmm_analysis.generate_threshold_recommendations import (
    _parse_output_spec,
)


def _recommendations_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "context": ["5min_trend_following"],
            "group_combo": ["structure+momentum"],
            "model": ["logistic"],
            "threshold": [0.5],
            "selected_fraction": [0.2],
            "mean_r_multiple_selected": [0.01],
            "win_rate_selected": [0.52],
            "lift_mean_r_multiple": [0.02],
            "lift_win_rate": [0.1],
            "gating_expression": ["true"],
        }
    )


def _profitability_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "context": ["5min_trend_following"],
            "group_combo": ["structure+momentum"],
            "model": ["gb_weighted"],
            "threshold": [0.53],
            "selected_fraction": [0.15],
            "mean_r_multiple_selected": [0.04],
            "win_rate_selected": [0.35],
            "lift_mean_r_multiple": [0.06],
            "lift_win_rate": [0.03],
        }
    )


def test_parse_output_spec_valid() -> None:
    overrides = _parse_output_spec(
        ["5min_trend_following=structure+momentum:gb_weighted:0.53"]
    )
    assert overrides == {
        "5min_trend_following": {
            "group": "structure+momentum",
            "model": "gb_weighted",
            "threshold": "0.53",
        }
    }


def test_context_output_override_replaces_row(tmp_path) -> None:
    recommendations = _recommendations_df()
    profitability = _profitability_df()
    rec_path = tmp_path / "recommendations.csv"
    prof_path = tmp_path / "profitability.csv"
    recommendations.to_csv(rec_path, index=False)
    profitability.to_csv(prof_path, index=False)

    overrides = {
        "5min_trend_following": {
            "group": "structure+momentum",
            "model": "gb_weighted",
            "threshold": "0.53",
        }
    }
    result = gen._apply_outputs_override(
        recommendations_df=pd.read_csv(rec_path),
        profitability_df=pd.read_csv(prof_path),
        output_overrides=overrides,
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["model"] == "gb_weighted"
    assert row["threshold"] == 0.53
    assert row["gating_expression"] == "true"
    assert row["selected_fraction"] == 0.15

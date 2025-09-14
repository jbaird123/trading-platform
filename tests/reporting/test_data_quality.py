from __future__ import annotations

import pandas as pd
from trading_platform.reporting.brief import compute_data_quality


def test_compute_data_quality_counts():
    idx = pd.to_datetime(
        ["2023-01-01 00:00:00", "2023-01-01 00:01:00", "2023-01-01 00:01:00"]
    )  # duplicate
    df = pd.DataFrame(
        {
            "open": [1.0, 2.0, 2.0],
            "high": [1.1, 2.1, 2.1],
            "low": [0.9, 1.9, 1.9],
            "close": [1.0, float("nan"), 2.0],
            "volume": [100, 200, 200],
        },
        index=idx,
    )
    dq = compute_data_quality(df)
    assert dq["index_monotonic_increasing"] is True
    assert dq["duplicate_bars_count"] == 1
    assert dq["nan_counts"]["close"] == 1
    assert dq["has_nans"] is True

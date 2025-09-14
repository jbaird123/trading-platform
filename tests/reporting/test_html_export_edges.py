from __future__ import annotations

from datetime import datetime

from trading_platform.reporting.html_export import _spark_svg, _to_ts


def test__to_ts_invalid_string_returns_min():
    out = _to_ts("not-a-date")
    assert isinstance(out, datetime) and out == datetime.min


def test__spark_svg_empty_series_returns_empty():
    assert _spark_svg([], {}, []) == ""

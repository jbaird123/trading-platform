"""CLI wrapper for threshold recommendation report builder."""

from __future__ import annotations

from trading_platform.rmm_analysis import (
    threshold_recommendation_report as _report,
)

if __name__ == "__main__":  # pragma: no cover
    _report.main()

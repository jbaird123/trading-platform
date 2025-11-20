from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

import pandas as pd

from trading_platform.portfolio.trade import Trade
from trading_platform.reporting import generate_brief

logger = logging.getLogger(__name__)


@dataclass
class ReportingTelemetry:
    brief_seconds: float
    trade_count: int


class ReportingPipeline:
    """Lightweight wrapper around generate_brief with telemetry + exports."""

    def __init__(
        self,
        *,
        initial_cash: float,
        meta: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        telemetry_logger: logging.Logger | None = None,
    ) -> None:
        self._initial_cash = float(initial_cash)
        self._meta = meta or {}
        self._params = params or {}
        self._telemetry_logger = telemetry_logger or logger
        self._telemetry: list[ReportingTelemetry] = []

    def build_brief(
        self,
        *,
        trades: Sequence[Trade],
        exposure_curve: list[tuple[datetime, float]] | None = None,
        skipped: list[dict[str, Any]] | None = None,
        config_snapshot: dict[str, Any] | None = None,
        instrument_definitions: dict[str, Any] | None = None,
        cost_model: dict[str, Any] | None = None,
        fill_policy: dict[str, Any] | None = None,
        tie_break_policy: dict[str, Any] | None = None,
        field_definitions: dict[str, Any] | None = None,
        data_quality: dict[str, Any] | None = None,
        signals_path: str | None = None,
        rmm_spans_path: str | None = None,
        processed_data_path: str | None = None,
        additional_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a brief and emit telemetry about the workload."""
        start = perf_counter()
        brief = generate_brief(
            meta={**self._meta, **(additional_meta or {})},
            params=self._params,
            trades=list(trades),
            initial_cash=self._initial_cash,
            exposure_curve=exposure_curve,
            config_snapshot=config_snapshot,
            instrument_definitions=instrument_definitions,
            cost_model=cost_model,
            fill_policy=fill_policy,
            tie_break_policy=tie_break_policy,
            data_quality=data_quality,
            skipped_trades=skipped,
            field_definitions=field_definitions,
            signals_path=signals_path,
            rmm_spans_path=rmm_spans_path,
            processed_data_path=processed_data_path,
        )
        elapsed = perf_counter() - start
        telemetry = ReportingTelemetry(
            brief_seconds=elapsed,
            trade_count=len(trades),
        )
        self._telemetry.append(telemetry)
        self._telemetry_logger.info(
            "reporting_metrics",
            extra={"brief_seconds": elapsed, "trade_count": len(trades)},
        )
        return brief

    @property
    def telemetry(self) -> list[ReportingTelemetry]:
        return list(self._telemetry)

    def trades_dataframe(self, trades: Sequence[Trade]) -> pd.DataFrame:
        """Create a pandas DataFrame suitable for validation exports."""
        rows: list[dict[str, Any]] = []
        for t in trades:
            rows.append(
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "size": t.size,
                    "pnl": t.pnl,
                    "exit_reason": t.exit_reason,
                    "context_at_entry": json.dumps(t.context_at_entry or {}),
                    "context_at_exit": json.dumps(t.context_at_exit or {}),
                }
            )
        return pd.DataFrame(rows)

    def export_validation_dataset(
        self, trades: Sequence[Trade], output_path: Path | str
    ) -> Path:
        """Write the validation-friendly CSV for golden comparisons."""
        df = self.trades_dataframe(trades)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return path


class ValidationHarness:
    """Deterministic hashing + comparison utilities for golden exports."""

    def __init__(self) -> None:
        self._hasher = hashlib.sha256

    def hash_dataframe(self, df: pd.DataFrame) -> str:
        payload = df.sort_index(axis=1).to_csv(index=False)
        return self._hasher(payload.encode("utf-8")).hexdigest()

    def compare(self, *, df: pd.DataFrame, expected_hash: str) -> dict[str, Any]:
        actual = self.hash_dataframe(df)
        return {
            "match": actual == expected_hash,
            "actual_hash": actual,
            "expected_hash": expected_hash,
        }


@dataclass
class RunArtifactCache:
    """Cache trades/brief payloads for Monte Carlo or WFE reuse."""

    _store: dict[str, dict[str, Any]] = field(default_factory=dict)

    def save(
        self,
        run_id: str,
        *,
        trades: Sequence[Trade],
        brief: dict[str, Any],
    ) -> None:
        self._store[run_id] = {
            "trades": deepcopy(list(trades)),
            "brief": deepcopy(brief),
        }

    def load(self, run_id: str) -> tuple[list[Trade], dict[str, Any]]:
        if run_id not in self._store:
            raise KeyError(f"Run '{run_id}' not cached.")
        data = self._store[run_id]
        return deepcopy(data["trades"]), deepcopy(data["brief"])

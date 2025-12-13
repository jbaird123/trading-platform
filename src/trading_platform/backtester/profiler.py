"""Performance profiling and timing instrumentation for backtester."""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""

    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestMetrics(StageMetrics):
    """Specialized metrics for the backtest execution stage."""

    bars_processed: int = 0
    bars_per_sec: float = 0.0
    avg_ms_per_bar: float = 0.0


@dataclass
class PerformanceProfile:
    """Complete performance profile for a backtest run."""

    timestamp: str
    total_duration_sec: float
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    enabled: bool = True


class PerformanceProfiler:
    """Context-manager based performance profiler with hierarchical timing."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        """Initialize profiler.

        Args:
            enabled: Override profiling state. If None, checks
                PROFILE_PERFORMANCE env var.
        """
        if enabled is None:
            enabled = os.environ.get("PROFILE_PERFORMANCE", "0") == "1"
        self._enabled = enabled
        self._stages: dict[str, StageMetrics] = {}
        self._start_time: float | None = None
        self._total_duration: float = 0.0

    @property
    def enabled(self) -> bool:
        """Check if profiling is enabled."""
        return self._enabled

    def start(self) -> None:
        """Start overall timing."""
        if self._enabled:
            self._start_time = perf_counter()

    def stop(self) -> None:
        """Stop overall timing."""
        if self._enabled and self._start_time is not None:
            self._total_duration = perf_counter() - self._start_time

    @contextmanager
    def stage(
        self, name: str, *, metadata: dict[str, Any] | None = None
    ) -> Iterator[None]:
        """Time a specific stage of the pipeline.

        Usage:
            with profiler.stage("load_data", metadata={"rows": 10000}):
                data = load_data()
        """
        if not self._enabled:
            yield
            return

        start = perf_counter()
        try:
            yield
        finally:
            duration_ms = (perf_counter() - start) * 1000
            self._stages[name] = StageMetrics(
                duration_ms=duration_ms,
                metadata=metadata or {},
            )

    def record_backtest_metrics(
        self,
        *,
        duration_ms: float,
        bars_processed: int,
        breakdown: dict[str, float] | None = None,
    ) -> None:
        """Record detailed backtest execution metrics."""
        if not self._enabled:
            return

        bars_per_sec = 0.0
        avg_ms_per_bar = 0.0
        if duration_ms > 0 and bars_processed > 0:
            duration_sec = duration_ms / 1000.0
            bars_per_sec = bars_processed / duration_sec
            avg_ms_per_bar = duration_ms / bars_processed

        metadata = {"breakdown": breakdown} if breakdown else {}
        self._stages["backtest"] = BacktestMetrics(
            duration_ms=duration_ms,
            bars_processed=bars_processed,
            bars_per_sec=bars_per_sec,
            avg_ms_per_bar=avg_ms_per_bar,
            metadata=metadata,
        )

    def get_profile(self) -> PerformanceProfile:
        """Get the complete performance profile."""
        stages_dict: dict[str, dict[str, Any]] = {}
        for name, metrics in self._stages.items():
            if isinstance(metrics, BacktestMetrics):
                stages_dict[name] = {
                    "duration_ms": metrics.duration_ms,
                    "bars_processed": metrics.bars_processed,
                    "bars_per_sec": metrics.bars_per_sec,
                    "avg_ms_per_bar": metrics.avg_ms_per_bar,
                    **metrics.metadata,
                }
            else:
                stages_dict[name] = {
                    "duration_ms": metrics.duration_ms,
                    **metrics.metadata,
                }

        return PerformanceProfile(
            timestamp=datetime.utcnow().isoformat(),
            total_duration_sec=self._total_duration,
            stages=stages_dict,
            enabled=self._enabled,
        )

    def write_json(self, output_path: Path | str) -> None:
        """Write performance profile to JSON file."""
        if not self._enabled:
            return

        profile = self.get_profile()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(asdict(profile), f, indent=2)

        logger.info(f"Performance profile written to {path}")

    def log_summary(self) -> None:
        """Log a human-readable summary to console."""
        if not self._enabled:
            return

        profile = self.get_profile()
        logger.info("=" * 60)
        logger.info("PERFORMANCE PROFILE")
        logger.info("=" * 60)
        logger.info(f"Total Duration: {profile.total_duration_sec:.2f}s")
        logger.info("")

        for stage_name, stage_data in profile.stages.items():
            duration_ms = stage_data.get("duration_ms", 0)
            duration_sec = duration_ms / 1000.0
            pct = (
                (duration_sec / profile.total_duration_sec * 100)
                if profile.total_duration_sec > 0
                else 0
            )

            logger.info(f"{stage_name}:")
            logger.info(f"  Duration: {duration_sec:.2f}s ({pct:.1f}%)")

            # Special handling for backtest metrics
            if "bars_per_sec" in stage_data:
                logger.info(f"  Bars Processed: {stage_data['bars_processed']:,}")
                logger.info(f"  Bars/sec: {stage_data['bars_per_sec']:.0f}")
                logger.info(f"  Avg ms/bar: {stage_data['avg_ms_per_bar']:.3f}")

                if "breakdown" in stage_data:
                    logger.info("  Breakdown:")
                    for sub_name, sub_ms in stage_data["breakdown"].items():
                        sub_pct = (sub_ms / duration_ms * 100) if duration_ms > 0 else 0
                        logger.info(f"    {sub_name}: {sub_ms:.0f}ms ({sub_pct:.1f}%)")

            # Log other metadata
            for key, value in stage_data.items():
                if key not in {
                    "duration_ms",
                    "bars_processed",
                    "bars_per_sec",
                    "avg_ms_per_bar",
                    "breakdown",
                }:
                    logger.info(f"  {key}: {value}")

            logger.info("")

        logger.info("=" * 60)

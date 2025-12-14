"""
DataHandler: Centralized data access with intelligent caching
and hierarchical resampling.

The DataHandler loads raw data once and maintains a cache of resampled timeframes.
When a new timeframe is requested, it intelligently resamples from the largest
cached timeframe that evenly divides into the target, minimizing computation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from trading_platform.data.instrument import (
    InstrumentDefinition,
    get_instrument_definition,
)
from trading_platform.data.session_metadata import (
    ALIGNED_TO_CLOSE_ATTR,
    SESSION_ATTR,
    annotate_session,
)

from .loader import load_instrument_data
from .schema import resample_ohlc

if TYPE_CHECKING:
    from .instrument import InstrumentDefinition


@dataclass
class _CachedInstrumentData:
    raw_data: pd.DataFrame
    data_quality_flags: list[str]
    cache: dict[str, pd.DataFrame]
    base_timeframe: str
    base_minutes: int
    loader_token: int


_GLOBAL_INSTRUMENT_CACHE: dict[tuple[str, Path], _CachedInstrumentData] = {}


def _parse_timeframe_to_minutes(timeframe: str) -> int:
    """Convert timeframe string to minutes.

    Examples:
        "1min" or "1T" -> 1
        "5min" or "5T" -> 5
        "1H" -> 60
        "4H" -> 240
        "1D" -> 1440
        "1W" -> 10080

    Args:
        timeframe: Timeframe string (e.g., "1H", "4H", "1D")

    Returns:
        Number of minutes in the timeframe

    Raises:
        ValueError: If timeframe format is invalid
    """
    tf = timeframe.strip().upper()

    # Handle minute formats
    if tf.endswith("MIN") or tf.endswith("T"):
        match = re.match(r"^(\d+)(MIN|T)$", tf)
        if match:
            return int(match.group(1))

    # Handle hour formats
    if tf.endswith("H"):
        match = re.match(r"^(\d+)H$", tf)
        if match:
            return int(match.group(1)) * 60

    # Handle day formats
    if tf.endswith("D"):
        match = re.match(r"^(\d+)D$", tf)
        if match:
            return int(match.group(1)) * 1440

    # Handle week formats
    if tf.endswith("W"):
        match = re.match(r"^(\d+)W$", tf)
        if match:
            return int(match.group(1)) * 10080

    raise ValueError(f"Invalid timeframe format: {timeframe}")


class DataHandler:
    """Centralized data handler with intelligent caching and hierarchical resampling.

    Loads raw data once and maintains a cache of resampled timeframes. When a new
    timeframe is requested, it resamples from the largest cached timeframe that
    evenly divides into the target, minimizing resampling work.

    All cached data contains the complete dataset (no partial/windowed caching) to
    ensure data integrity when resampling from cached timeframes.
    """

    def __init__(
        self,
        symbol: str,
        data_root: Path,
        instrument: InstrumentDefinition | None = None,
    ):
        """Initialize DataHandler.

        Args:
            symbol: Financial instrument symbol (e.g., "EURUSD")
            data_root: Root directory containing data files
            instrument: Instrument definition for session-aware resampling
        """
        resolved_root = Path(data_root).resolve()
        self.symbol = symbol
        self.data_root = resolved_root

        if instrument is None:
            try:
                instrument = get_instrument_definition(symbol)
            except ValueError:
                instrument = InstrumentDefinition(
                    asset_class="Synthetic",
                    session_group="forex",
                    point_value=1.0,
                    tick_size=0.00001,
                    pip_location=None,
                    commission_model={"type": "synthetic"},
                    sessions=[],
                    symbol=symbol,
                )

        self.instrument = instrument
        self._session = instrument.sessions[0] if instrument.sessions else None

        cache_key = (symbol, resolved_root)
        cached = _GLOBAL_INSTRUMENT_CACHE.get(cache_key)

        loader_token = id(load_instrument_data)
        needs_reload = cached is None or cached.loader_token != loader_token

        if needs_reload:
            raw_data, dq_flags = load_instrument_data(symbol, resolved_root)
            annotate_session(raw_data, self._session)
            base_timeframe, base_minutes = self._detect_base_timeframe_from_df(raw_data)
            cache_dict: dict[str, pd.DataFrame] = {base_timeframe: raw_data}
            cached = _CachedInstrumentData(
                raw_data=raw_data,
                data_quality_flags=dq_flags,
                cache=cache_dict,
                base_timeframe=base_timeframe,
                base_minutes=base_minutes,
                loader_token=loader_token,
            )
            _GLOBAL_INSTRUMENT_CACHE[cache_key] = cached
        else:
            assert cached is not None  # narrow type for static analyzers
            annotate_session(cached.raw_data, self._session)

        # Load raw data once (shared across handler instances)
        # Ensure the base data is explicitly aligned to bar_close and carries
        # bar_open/bar_close columns so downstream consumers never need to
        # infer timestamps.
        aligned_base = self._ensure_close_aligned(
            cached.raw_data, cached.base_timeframe, cached.base_minutes
        )
        cached.raw_data = aligned_base
        cached.cache[cached.base_timeframe] = aligned_base

        self._raw_data = aligned_base
        self.data_quality_flags = cached.data_quality_flags

        # Cache: timeframe_str -> full_dataframe (shared per instrument)
        self._cache = cached.cache

        # RMM context cache: (rmm_config_hash, timeframe) -> rmm_context_dict
        # Caches regime classification results to avoid recomputation
        self._rmm_cache: dict[tuple[str, str], dict] = {}

        # Detect base timeframe from raw data instead of assuming
        self._base_timeframe = cached.base_timeframe
        self._base_minutes = cached.base_minutes

    def get_data(
        self,
        timeframe: str | None = None,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Get data for the specified timeframe and date range.

        The complete dataset for the timeframe is cached. Date filtering is applied
        only when returning data to the caller, ensuring cache can be reused across
        different date range requests.

        Args:
            timeframe: Target timeframe (e.g., "1H", "4H", "1D").
                If None, returns base data.
            start: Start date/time for filtering. If None, returns from beginning.
            end: End date/time for filtering. If None, returns to end.

        Returns:
            DataFrame with OHLCV data for the requested timeframe and date range
        """
        # If no timeframe specified, use raw data
        if timeframe is None:
            df = self._raw_data
        else:
            # Normalize timeframe string
            timeframe = timeframe.strip().lower()

            # Check if already cached
            if timeframe not in self._cache:
                df_source = self._find_best_resample_source(timeframe)
                df_resampled = resample_ohlc(
                    df_source, timeframe, session=self._session
                )
                if df_resampled.empty:
                    df_resampled = df_source.copy()

                annotate_session(df_resampled, self._session)
                self._cache[timeframe] = df_resampled

            df = self._cache[timeframe]

        # Normalize to explicit bar_open/bar_close with bar_close index
        df = self._ensure_close_aligned(
            df,
            timeframe if timeframe is not None else self._base_timeframe,
            None,
        )
        # Persist normalized view in cache for reuse
        cache_key = timeframe if timeframe is not None else self._base_timeframe
        self._cache[cache_key] = df

        # Apply date filtering if requested
        if start is not None:
            start_ts = pd.to_datetime(start, utc=True)
            df = df.loc[start_ts:]

        if end is not None:
            end_ts = pd.to_datetime(end, utc=True)
            df = df.loc[:end_ts]

        return df

    @staticmethod
    def _detect_base_timeframe_from_df(df: pd.DataFrame) -> tuple[str, int]:
        """Detect the base timeframe of the provided dataframe.

        Args:
            df: DataFrame indexed by datetime containing at least two bars

        Returns:
            Tuple of (timeframe_string, minutes)

        Raises:
            ValueError: If the dataframe contains fewer than two rows or the
                resulting cadence cannot be mapped to a supported timeframe.
        """
        if len(df) < 2:
            raise ValueError(
                "Cannot detect base timeframe: need at least two bars "
                f"but received {len(df)}."
            )

        index = df.index
        if not isinstance(index, pd.DatetimeIndex):
            raise TypeError(
                "Expected a DatetimeIndex to detect base timeframe, "
                f"received {type(index)}."
            )

        # Calculate time differences between consecutive bars
        time_diffs = index[1:] - index[:-1]
        most_common_diff = time_diffs.value_counts().idxmax()

        timedelta = pd.Timedelta(most_common_diff)
        minutes = int(timedelta.total_seconds() / 60)

        mapping: dict[int, str] = {
            1: "1min",
            5: "5min",
            15: "15min",
            60: "1h",
            240: "4h",
            1440: "1d",
            10080: "1w",
        }

        timeframe = mapping.get(minutes)
        if timeframe is None:
            raise ValueError(
                f"Detected unsupported timeframe: {minutes} minutes between bars."
            )
        return timeframe, minutes

    def _detect_base_timeframe(self) -> tuple[str, int]:
        """Detect the base timeframe of the raw data.

        Analyzes the time differences between consecutive bars to determine
        the native resolution of the loaded data.

        Returns:
            Tuple of (timeframe_string, minutes)

        Raises:
            ValueError: If timeframe cannot be detected or data is irregular
        """
        return self._detect_base_timeframe_from_df(self._raw_data)

    def _find_best_resample_source(self, target_timeframe: str) -> pd.DataFrame:
        """Find the largest cached timeframe that evenly divides into target.

        This minimizes resampling work by using the highest-resolution cached data
        that can produce the target timeframe without introducing artifacts.

        Args:
            target_timeframe: Target timeframe string (e.g., "4H")

        Returns:
            DataFrame from the best cached source for resampling

        Raises:
            ValueError: If no suitable source exists
                (i.e., requesting higher resolution than base)
        """
        target_minutes = _parse_timeframe_to_minutes(target_timeframe)

        # Check if requesting finer resolution than base data
        if target_minutes < self._base_minutes:
            raise ValueError(
                f"Cannot resample to {target_timeframe} ({target_minutes} min): "
                f"base data resolution is {self._base_timeframe} "
                f"({self._base_minutes} min). Cannot create higher resolution "
                f"data from lower resolution source."
            )

        # Get all cached timeframes with their minute values
        cached_options = []
        for cached_tf in self._cache.keys():
            try:
                cached_minutes = _parse_timeframe_to_minutes(cached_tf)
                cached_options.append((cached_minutes, cached_tf))
            except ValueError:
                # Skip any invalid cached timeframes
                continue

        # Sort by minutes descending (largest first)
        cached_options.sort(reverse=True)

        # Find largest cached timeframe that evenly divides into target
        for cached_minutes, cached_tf in cached_options:
            if (
                cached_minutes <= target_minutes
                and target_minutes % cached_minutes == 0
            ):
                return self._cache[cached_tf]

        # Should never reach here since base data should always be in cache
        # and should evenly divide into target (we checked above)
        raise ValueError(
            f"Internal error: no suitable resample source found for "
            f"{target_timeframe}. Base timeframe: {self._base_timeframe}, "
            f"cached: {list(self._cache.keys())}"
        )

    def get_cached_timeframes(self) -> list[str]:
        """Get list of currently cached timeframes.

        Returns:
            List of timeframe strings currently in cache
        """
        return list(self._cache.keys())

    def get_rmm_context(
        self,
        rmm_config: dict,
        timeframe: str,
    ) -> dict | None:
        """Get cached RMM context if available.

        Args:
            rmm_config: RMM configuration dict
            timeframe: Regime classification timeframe

        Returns:
            Cached RMM context dict, or None if not cached
        """
        import hashlib
        import json

        # Create stable hash of RMM config for cache key
        config_str = json.dumps(rmm_config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()

        cache_key = (config_hash, timeframe)
        return self._rmm_cache.get(cache_key)

    def set_rmm_context(
        self,
        rmm_config: dict,
        timeframe: str,
        rmm_context: dict,
    ) -> None:
        """Cache RMM context for future use.

        Args:
            rmm_config: RMM configuration dict
            timeframe: Regime classification timeframe
            rmm_context: Computed RMM context to cache
        """
        import hashlib
        import json

        # Create stable hash of RMM config for cache key
        config_str = json.dumps(rmm_config, sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()

        cache_key = (config_hash, timeframe)
        self._rmm_cache[cache_key] = rmm_context

    def clear_cache(self, keep_base: bool = True) -> None:
        """Clear the timeframe cache.

        Args:
            keep_base: If True, keeps the base raw data in cache.
                If False, clears everything.
        """
        if keep_base:
            self._cache = {self._base_timeframe: self._raw_data}
        else:
            self._cache = {}
        # Always clear RMM cache when clearing
        self._rmm_cache = {}

    def _ensure_close_aligned(
        self,
        df: pd.DataFrame,
        timeframe: str,
        minutes: int | None = None,
    ) -> pd.DataFrame:
        """Return a copy of df with explicit bar_open/bar_close and bar_close index."""
        if df.empty:
            return df

        base_minutes_attr = getattr(self, "_base_minutes", None)
        base_minutes = (
            int(base_minutes_attr) if isinstance(base_minutes_attr, int) else None
        )
        tf_minutes: int
        try:
            parsed_tf = _parse_timeframe_to_minutes(timeframe)
        except Exception:
            parsed_tf = None
        if minutes is not None:
            tf_minutes = int(minutes)
        elif parsed_tf is not None:
            tf_minutes = int(parsed_tf)
        elif base_minutes is not None:
            tf_minutes = int(base_minutes)
        else:
            idx = pd.DatetimeIndex(df.index)
            if len(idx) >= 2:
                tf_minutes = int((idx[1] - idx[0]).total_seconds() / 60)
            else:
                tf_minutes = 0
        delta = pd.Timedelta(minutes=tf_minutes)
        session = self._session

        # Work on a copy to avoid mutating shared cache unexpectedly
        result = df.copy()

        has_open = "bar_open" in result.columns
        has_close = "bar_close" in result.columns

        if has_open and has_close:
            bar_open = pd.DatetimeIndex(pd.to_datetime(result["bar_open"], utc=True))
            bar_close = pd.DatetimeIndex(pd.to_datetime(result["bar_close"], utc=True))
        else:
            idx = pd.DatetimeIndex(result.index)
            aligned_to_close = bool(result.attrs.get(ALIGNED_TO_CLOSE_ATTR, False))
            if aligned_to_close:
                bar_close = idx
                bar_open = idx - delta
            else:
                bar_open = idx
                bar_close = idx + delta

        result["bar_open"] = bar_open
        result["bar_close"] = bar_close
        result["open_time"] = bar_open
        result["close_time"] = bar_close
        # Name the index to avoid clashing with bar_close column label
        result.index = pd.DatetimeIndex(bar_close, name="timestamp")
        result.attrs[ALIGNED_TO_CLOSE_ATTR] = True
        if session is not None:
            result.attrs[SESSION_ATTR] = session
        return result

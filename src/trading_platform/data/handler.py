"""
DataHandler: Centralized data access with intelligent caching
and hierarchical resampling.

The DataHandler loads raw data once and maintains a cache of resampled timeframes.
When a new timeframe is requested, it intelligently resamples from the largest
cached timeframe that evenly divides into the target, minimizing computation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from .loader import load_instrument_data
from .schema import resample_ohlc

if TYPE_CHECKING:
    from .instrument import InstrumentDefinition


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
            symbol: Financial instrument symbol (e.g., "EUR_USD")
            data_root: Root directory containing data files
            instrument: Instrument definition for session-aware resampling
        """
        self.symbol = symbol
        self.data_root = data_root
        self.instrument = instrument

        # Load raw data once
        self._raw_data, self.data_quality_flags = load_instrument_data(
            symbol, data_root
        )

        # Cache: timeframe_str -> full_dataframe
        # All cached data contains the complete dataset
        self._cache: dict[str, pd.DataFrame] = {}

        # RMM context cache: (rmm_config_hash, timeframe) -> rmm_context_dict
        # Caches regime classification results to avoid recomputation
        self._rmm_cache: dict[tuple[str, str], dict] = {}

        # Detect base timeframe from raw data instead of assuming
        self._base_timeframe, self._base_minutes = self._detect_base_timeframe()
        self._cache[self._base_timeframe] = self._raw_data

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
                # Need to resample - find best source
                df_source = self._find_best_resample_source(timeframe)

                # Resample complete dataset and cache it
                df_resampled = resample_ohlc(df_source, timeframe, self.instrument)
                self._cache[timeframe] = df_resampled

            df = self._cache[timeframe]

        # Apply date filtering if requested
        if start is not None:
            start_ts = pd.to_datetime(start, utc=True)
            df = df.loc[start_ts:]

        if end is not None:
            end_ts = pd.to_datetime(end, utc=True)
            df = df.loc[:end_ts]

        return df

    def _detect_base_timeframe(self) -> tuple[str, int]:
        """Detect the base timeframe of the raw data.

        Analyzes the time differences between consecutive bars to determine
        the native resolution of the loaded data.

        Returns:
            Tuple of (timeframe_string, minutes)

        Raises:
            ValueError: If timeframe cannot be detected or data is irregular
        """
        if len(self._raw_data) < 2:
            raise ValueError(
                f"Cannot detect base timeframe: need at least 2 bars, "
                f"got {len(self._raw_data)}"
            )

        # Calculate time differences between consecutive bars
        time_diffs = self._raw_data.index[1:] - self._raw_data.index[:-1]

        # Get the most common difference (mode)
        most_common_diff = time_diffs.value_counts().idxmax()

        # Convert to minutes
        minutes = int(most_common_diff.total_seconds() / 60)

        # Map to standard timeframe string
        if minutes == 1:
            return ("1min", 1)
        elif minutes == 5:
            return ("5min", 5)
        elif minutes == 15:
            return ("15min", 15)
        elif minutes == 60:
            return ("1h", 60)
        elif minutes == 240:
            return ("4h", 240)
        elif minutes == 1440:
            return ("1d", 1440)
        else:
            raise ValueError(
                f"Detected unusual timeframe: {minutes} minutes. "
                f"Expected standard timeframes: 1min, 5min, 15min, 1h, 4h, or 1d"
            )

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

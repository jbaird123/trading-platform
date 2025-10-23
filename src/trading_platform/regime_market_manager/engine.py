from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from trading_platform.data.schema import resample_ohlc
from trading_platform.regime_market_manager.models import RMMConfig
from trading_platform.strategy.features import compute_features


def _op_series(df: pd.DataFrame, operand: Any) -> pd.Series:
    if isinstance(operand, (int, float)):
        return pd.Series([float(operand)] * len(df), index=df.index)
    if isinstance(operand, str) and operand in df.columns:
        return pd.Series(df[operand], dtype="float64")
    if isinstance(operand, dict) and "ref" in operand:
        name = str(operand["ref"])
        return pd.Series(df[name], dtype="float64")
    return pd.Series([0.0] * len(df), index=df.index)


def _eval_pred(df: pd.DataFrame, pred: dict[str, Any]) -> pd.Series:
    cond = str(pred.get("condition"))
    left = _op_series(df, pred.get("left"))
    right = _op_series(df, pred.get("right"))
    if cond == "is_above":
        return left > right
    if cond == "is_below":
        return left < right
    if cond == "cross_above":
        # True when left crosses from below to above right
        above_now = left > right
        above_shifted = (left > right).shift(1)
        # Fill with True to avoid downcasting warning, then convert to bool
        above_prev = above_shifted.fillna(value=True).astype(bool)
        # First bar can't be a cross (no previous to compare)
        result = above_now & ~above_prev
        result.iloc[0] = False
        return result
    if cond == "cross_below":
        # True when left crosses from above to below right
        below_now = left < right
        below_shifted = (left < right).shift(1)
        # Fill with True to avoid downcasting warning, then convert to bool
        below_prev = below_shifted.fillna(value=True).astype(bool)
        # First bar can't be a cross (no previous to compare)
        result = below_now & ~below_prev
        result.iloc[0] = False
        return result
    if cond == "hour_is_in":
        values = set(pred.get("values", []))
        dt_index = pd.DatetimeIndex(df.index)
        return pd.Series(dt_index.hour.isin(values), index=df.index)
    if cond == "hour_is_not_in":
        values = set(pred.get("values", []))
        dt_index = pd.DatetimeIndex(df.index)
        return pd.Series(~dt_index.hour.isin(values), index=df.index)
    if cond == "day_of_week_is_in":
        # Monday=0, Sunday=6
        values = set(pred.get("values", []))
        dt_index = pd.DatetimeIndex(df.index)
        return pd.Series(dt_index.dayofweek.isin(values), index=df.index)
    if cond == "day_of_week_is_not_in":
        values = set(pred.get("values", []))
        dt_index = pd.DatetimeIndex(df.index)
        return pd.Series(~dt_index.dayofweek.isin(values), index=df.index)
    if cond == "percentile_is_above":
        # For percentile predicates, left is already a percentile (0-100)
        # right is the threshold percentile value
        return left > right
    if cond == "volatility_is_between":
        # Check if volatility is between lower and upper bounds
        lower = float(pred.get("lower", 0.0))
        upper = float(pred.get("upper", 1.0))
        return (left >= lower) & (left <= upper)
    # SAFETY: Fail loudly on unrecognized conditions
    raise ValueError(
        f"Unrecognized RMM condition: '{cond}'. "
        f"Supported: is_above, is_below, cross_above, cross_below, "
        f"hour_is_in, hour_is_not_in, day_of_week_is_in, "
        f"day_of_week_is_not_in, percentile_is_above, volatility_is_between"
    )


def _eval_block(df: pd.DataFrame, block: dict[str, Any]) -> pd.Series:
    if "all_of" in block:
        out = pd.Series([True] * len(df), index=df.index)
        for p in block.get("all_of") or []:
            out = out & _eval_pred(df, p)
        return out
    if "any_of" in block:
        out = pd.Series([False] * len(df), index=df.index)
        for p in block.get("any_of") or []:
            out = out | _eval_pred(df, p)
        return out
    return pd.Series([False] * len(df), index=df.index)


@dataclass(frozen=True)
class RMMEngine:
    config: RMMConfig

    def classify_regime(
        self,
        df_data: pd.DataFrame,
        timeframe: str | None = None,
        already_resampled: bool = False,
    ) -> pd.DataFrame:
        """Return regime labels/confidence based on RMM config rules.

        Args:
            df_data: Input OHLCV data (any timeframe)
            timeframe: Regime classification timeframe (e.g., "1D", "4H", "1H").
                If None, uses timeframe from config. Defaults to "1D" if not
                specified.
            already_resampled: If True, assumes df_data is already at the target
                timeframe. Used when DataHandler provides pre-resampled data for
                performance.

        Returns:
            DataFrame with: label, confidence, and all computed regime features.
        """
        cfg = self.config.model_dump(exclude_none=True)
        feats = list(cfg.get("features") or [])
        regimes = list(cfg.get("regimes") or [])

        # Get timeframe from parameter, config, or default to "1D"
        if timeframe is None:
            timeframe = cfg.get("timeframe", "1D")

        # Resample to regime timeframe (unless caller already resampled via DataHandler)
        if already_resampled:
            resampled = df_data
        else:
            resampled = resample_ohlc(df_data, timeframe.lower())

        # PERFORMANCE: Compute features once on full DataFrame (vectorized)
        df = compute_features(resampled, feats)

        # PERFORMANCE: Evaluate regime conditions vectorized (no per-bar loop)
        raw_labels = pd.Series(
            ["unknown"] * len(df), index=df.index, dtype="object"
        )
        raw_confs = pd.Series([0.0] * len(df), index=df.index, dtype="float64")

        # Evaluate each regime's conditions as vectorized boolean masks
        for r in regimes:
            conds = r.get("conditions") or {}
            mask = _eval_block(df, conds)  # Returns boolean Series for all bars
            label = str(r.get("label"))
            confidence = float(r.get("confidence", 0.0))

            # Update labels/confidence where this regime's conditions are true
            # and no higher-priority regime has already been assigned
            # (regimes are checked in order, first match wins)
            update_mask = mask & (raw_labels == "unknown")
            raw_labels.loc[update_mask] = label
            raw_confs.loc[update_mask] = confidence

        hysteresis_cfg = cfg.get("hysteresis") or {}
        (
            adj_labels,
            adj_confs,
            bars_in_state,
            cooldown_remaining,
        ) = self._apply_hysteresis(raw_labels, raw_confs, hysteresis_cfg)

        # Include computed features alongside label and confidence
        out: pd.DataFrame = df.copy()
        out["raw_label"] = raw_labels
        out["raw_confidence"] = raw_confs
        out["label"] = adj_labels
        out["confidence"] = adj_confs
        out["bars_in_state"] = bars_in_state
        out["cooldown_remaining"] = cooldown_remaining
        return out

    @staticmethod
    def _apply_hysteresis(
        raw_labels: pd.Series,
        raw_confs: pd.Series,
        cfg: dict[str, Any],
    ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """Apply hysteresis rules to raw regime labels."""
        if not isinstance(cfg, dict):
            cfg = {}

        min_bars = int(cfg.get("min_bars", 0) or 0)
        cooldown_bars = int(cfg.get("cooldown_bars", 0) or 0)

        if min_bars == 0 and cooldown_bars == 0:
            zeros = pd.Series(
                [0] * len(raw_labels), index=raw_labels.index, dtype="int64"
            )
            return (
                raw_labels.copy(),
                raw_confs.copy(),
                zeros.copy(),
                zeros.copy(),
            )

        adj_labels: list[str] = []
        adj_confs: list[float] = []
        bars_history: list[int] = []
        cooldown_history: list[int] = []

        active_label = "unknown"
        active_conf = 0.0
        bars_in_state = 0
        cooldown_remaining = 0

        for raw_label, raw_conf in zip(
            raw_labels.tolist(),
            raw_confs.tolist(),
        ):
            raw_conf_value = float(raw_conf)

            if active_label == "unknown" and raw_label != "unknown":
                active_label = raw_label
                active_conf = raw_conf_value
                bars_in_state = 0
                cooldown_remaining = 0
            elif raw_label == active_label:
                active_conf = raw_conf_value
                bars_in_state += 1
                if cooldown_remaining > 0:
                    cooldown_remaining -= 1
            else:
                if cooldown_remaining > 0:
                    cooldown_remaining -= 1
                    bars_in_state += 1
                elif bars_in_state < min_bars:
                    bars_in_state += 1
                else:
                    active_label = raw_label
                    active_conf = raw_conf_value
                    bars_in_state = 0
                    cooldown_remaining = cooldown_bars

            adj_labels.append(active_label)
            adj_confs.append(active_conf)
            bars_history.append(bars_in_state)
            cooldown_history.append(cooldown_remaining)

        index = raw_labels.index
        labels_series = pd.Series(adj_labels, index=index, dtype="object")
        confs_series = pd.Series(adj_confs, index=index, dtype="float64")
        bars_series = pd.Series(bars_history, index=index, dtype="int64")
        cooldown_series = pd.Series(
            cooldown_history, index=index, dtype="int64"
        )

        return labels_series, confs_series, bars_series, cooldown_series

    def classify_daily(self, df_hourly: pd.DataFrame) -> pd.DataFrame:
        """Return daily regime labels/confidence based on RMM config rules.

        DEPRECATED: Use classify_regime() instead for multi-timeframe support.
        This method is kept for backward compatibility.

        Returns DataFrame with: label, confidence, and all computed regime features.
        """
        return self.classify_regime(df_hourly, "1D")

    @staticmethod
    def allowed_sides_for(label: str, confidence: float, policy: dict) -> list[str]:
        """Decide allowed sides based on policy + conventional mapping.

        Policy (per schema):
        - min_confidence: float
        - allow_labels: [str]
        - block_labels: [str]

        Conventional mapping:
        - trend_up -> ["long"]
        - trend_down -> ["short"]
        - range/other -> ["long", "short"] (if label passes policy checks)
        """
        min_c = (
            float(policy.get("min_confidence", 0.0))
            if isinstance(policy, dict)
            else 0.0
        )
        if confidence < min_c:
            return []
        allow_labels = policy.get("allow_labels") or None
        if isinstance(allow_labels, list) and label not in allow_labels:
            return []
        block_labels = policy.get("block_labels") or None
        if isinstance(block_labels, list) and label in block_labels:
            return []
        if label == "trend_up":
            return ["long"]
        if label == "trend_down":
            return ["short"]
        # For non-directional labels (range, unknown, etc.) that pass policy checks,
        # allow both sides. This enables range-based or neutral regime strategies.
        return ["long", "short"]

    def project_to_index(
        self, daily: pd.DataFrame, target_index: pd.DatetimeIndex, policy: dict | None
    ) -> pd.DataFrame:
        """Forward-fill daily regimes onto target index with allowed sides.

        Returns DataFrame with all columns from daily (including regime features)
        plus allowed_sides, indexed by target_index.

        IMPORTANT: Shifts regime data by 1 bar to prevent lookahead bias.
        At time T, we use the regime from the previous completed bar, not the
        bar that's currently in progress.
        """
        if daily.empty:
            df = pd.DataFrame(index=target_index)
            df["label"] = "unknown"
            df["confidence"] = 0.0
            df["raw_label"] = "unknown"
            df["raw_confidence"] = 0.0
            df["bars_in_state"] = 0
            df["cooldown_remaining"] = 0
            empty_allowed: list[list[str]] = [
                [] for _ in range(len(target_index))
            ]
            df["allowed_sides"] = empty_allowed  # pyright: ignore
            return df

        # CRITICAL: Shift regime data by 1 bar to prevent lookahead bias
        # This ensures we only use regime information from COMPLETED bars.
        # Example: At 10:05 on a 5min chart with 15min RMM:
        #   - Without shift: would use regime from 10:00 bar (not closed until 10:15) ❌
        #   - With shift: uses regime from 09:45 bar (closed at 10:00) ✅
        daily_shifted = daily.shift(1)

        # Reindex with forward-fill to align to target_index boundaries
        # This preserves all columns including regime features
        aligned = (
            daily_shifted.reindex(daily_shifted.index.union(target_index))
            .sort_index()
            .ffill()
        )
        aligned = aligned.loc[target_index]
        defaults: dict[str, Any] = {
            "raw_label": "unknown",
            "raw_confidence": 0.0,
            "bars_in_state": 0,
            "cooldown_remaining": 0,
        }
        for col, default in defaults.items():
            if col not in aligned.columns:
                aligned[col] = default

        aligned["raw_label"] = aligned["raw_label"].fillna("unknown").astype("object")
        aligned["raw_confidence"] = (
            aligned["raw_confidence"].fillna(0.0).astype("float64")
        )
        aligned["bars_in_state"] = (
            aligned["bars_in_state"].fillna(0).astype("int64")
        )
        aligned["cooldown_remaining"] = (
            aligned["cooldown_remaining"].fillna(0).astype("int64")
        )

        allowed = [
            self.allowed_sides_for(
                str(row["label"]), float(row["confidence"]), policy or {}
            )
            for _, row in aligned.iterrows()
        ]
        aligned = aligned.assign(
            allowed_sides=pd.Series(allowed, index=aligned.index, dtype=object)
        )
        return aligned

#!/usr/bin/env bash
set -euo pipefail

# Run with Poetry when available; otherwise use system Python with PYTHONPATH
if command -v poetry >/dev/null 2>&1; then
  CMD=(poetry run python)
else
  PY_BIN="${PYTHON:-python}"
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then PY_BIN="python3"; else
      echo "Missing python; set \$PYTHON or install python." >&2; exit 1; fi
  fi
  CMD=(env PYTHONPATH="src:${PYTHONPATH:-}" "$PY_BIN")
fi

"${CMD[@]}" - <<'PY'
import yaml
from pathlib import Path
from trading_platform.data.loader import load_from_catalog
from trading_platform.data.schema import resample_ohlc
from trading_platform.strategy.features import compute_features, adx
from trading_platform.regime_market_manager.engine import RMMEngine

# Inputs
symbol = "EUR_USD"
timeframe = "1H"
start = "2021-01-01"
end = "2023-03-01"

# Load hourly, resample to daily (UTC)
df_hourly, _ = load_from_catalog({
    "symbol": symbol, "timeframe": timeframe, "start": start, "end": end
})
daily = resample_ohlcv = resample_ohlc(df_hourly, "1D")

# Load RMM config and compute daily features (EMA fast/slow, ADX)
rmm_cfg = yaml.safe_load(open("config/rmm/daily_trend.yaml"))
feats = compute_features(daily, rmm_cfg.get("features") or [])

# Ensure an ADX column exists (name as in the RMM config: d_adx)
if "d_adx" not in feats.columns:
    length = int((rmm_cfg["features"][2].get("params") or {}).get("length", 14))
    feats["d_adx"] = adx(daily, length)

# Classify regimes daily and project to daily index with policy
engine = RMMEngine(config=rmm_cfg)
labels_daily = engine.classify_daily(df_hourly)
policy = rmm_cfg.get("policy") or {}
proj_daily = engine.project_to_index(labels_daily, daily.index, policy=policy)

# Assemble output
out = daily[["open", "high", "low", "close", "volume"]].copy()

for col in ["d_ema_fast", "d_ema_slow", "d_adx"]:
    if col in feats.columns:
        out[col] = feats[col]

out["rmm_label"] = proj_daily["label"]
out["rmm_confidence"] = proj_daily["confidence"]
out["rmm_allowed_sides"] = proj_daily["allowed_sides"]
out["rmm_policy_min_conf"] = float(policy.get("min_confidence", 0.0))

out_dir = Path("runs") / "researcher" / "diagnostics"
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"daily_dump_{symbol}_{start}_to_{end}.csv"
out.to_csv(out_path, index_label="timestamp")
print(f"Wrote: {out_path}")
print(out.head(5))
PY

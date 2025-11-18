# Proposed Global Feature Set and Rationale

This document contains a proposed comprehensive feature set for the `global.yaml` file and a detailed explanation of the design choices behind it.

---

## Proposed `global.yaml` Content

```yaml
# Global features that are ALWAYS included in every backtest context.
# This feature set is designed to provide a rich, multi-timeframe view of
# market trend, momentum, volatility, and volume.
#
# Feature names MUST have a timeframe prefix (15min_, 1h_, 4h_, 1d_).

features:
  # --- Trend Indicators ---
  # Provide a view of the trend across major timeframes.
  - name: "15min_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "15min"
  - name: "1h_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1H"
  - name: "4h_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "4H"
  - name: "1d_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1D"
  - name: "1w_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1W"
  - name: "1h_adx_14"
    type: "ADX"
    params: { "length": 14 }
    timeframe: "1H"
  - name: "4h_adx_14"
    type: "ADX"
    params: { "length": 14 }
    timeframe: "4H"
  - name: "1d_adx_14"
    type: "ADX"
    params: { "length": 14 }
    timeframe: "1D"
  - name: "1w_adx_14"
    type: "ADX"
    params: { "length": 14 }
    timeframe: "1W"

  # --- Momentum Indicators ---
  # Measure the speed and change of price movements.
  - name: "15min_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "15min"
  - name: "1h_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "1H"
  - name: "4h_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "4H"
  - name: "1d_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "1D"
  - name: "1w_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "1W"
  - name: "1h_macd"
    type: "MACD"
    params: { "fast": 12, "slow": 26, "signal": 9 }
    timeframe: "1H"
  - name: "4h_macd"
    type: "MACD"
    params: { "fast": 12, "slow": 26, "signal": 9 }
    timeframe: "4H"
  - name: "1d_macd"
    type: "MACD"
    params: { "fast": 12, "slow": 26, "signal": 9 }
    timeframe: "1D"
  - name: "1w_macd"
    type: "MACD"
    params: { "fast": 12, "slow": 26, "signal": 9 }
    timeframe: "1W"

  # --- Volatility Indicators ---
  # Measure the magnitude of price fluctuations.
  - name: "15min_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "15min"
  - name: "1h_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1H"
  - name: "4h_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "4H"
  - name: "1d_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1D"
  - name: "1w_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1W"
  - name: "1h_bb_width_20"
    type: "BBWidth"
    params: { "length": 20, "ndev": 2.0 }
    timeframe: "1H"
  - name: "4h_bb_width_20"
    type: "BBWidth"
    params: { "length": 20, "ndev": 2.0 }
    timeframe: "4H"
  - name: "1d_bb_width_20"
    type: "BBWidth"
    params: { "length": 20, "ndev": 2.0 }
    timeframe: "1D"

  # --- Volume Indicators ---
  # Measure market participation and conviction.
  - name: "15min_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "15min"
  - name: "1h_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1H"
  - name: "4h_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "4H"
  - name: "1d_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1D"
  - name: "1w_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1W"
  - name: "1h_obv"
    type: "OBV"
    params: {} # OBV has no length parameter
    timeframe: "1H"
  - name: "1d_obv"
    type: "OBV"
    params: {}
    timeframe: "1D"
  - name: "1w_obv"
    type: "OBV"
    params: {}
    timeframe: "1W"
```

---

## Rationale for Feature Selection

### 1. Overall Goal

The primary goal of this feature set is to provide any AI model with a rich, holistic, and multi-timeframe understanding of the market context for any given trade. The selection prioritizes well-understood, computationally efficient indicators while avoiding excessive redundancy.

### 2. Multi-Timeframe Analysis

A core principle of this design is providing symmetric coverage across the full stack of horizons (`15min`, `1H`, `4H`, `1D`, `1W`). This lets the AI understand how a low-timeframe setup sits inside the higher-timeframe regime and, conversely, gives higher-timeframe trades enough local detail to evaluate execution quality.

### 3. Feature Categories

The features are grouped into four essential categories to give a complete picture of market dynamics:

#### Trend Indicators
*   **Selection:** `EMA(50)` on `15m`, `1H`, `4H`, `1D`, and `1W`; `ADX(14)` on the same five timeframes.
*   **Rationale:** These pairs give the AI a consistent read on direction and trend strength from tactical (15 min) through macro (weekly). Lower-timeframe trades still see the higher-context regime, and higher-timeframe trades now have sufficient coverage.

#### Momentum Indicators
*   **Selection:** `RSI(14)` and `MACD(12,26,9)` across all major timeframes (15m → 1W).
*   **Rationale:** RSI continues to flag overbought/oversold dynamics at each horizon, while MACD delivers crossover and slope information. Weekly momentum data helps a daily strategy detect long-cycle exhaustion.

#### Volatility Indicators
*   **Selection:** `ATR(14)` on every timeframe plus `BBWidth(20, 2.0)` on `1H`, `4H`, and `1D`.
*   **Rationale:** ATR supplies a canonical risk distance across horizons. Bollinger width highlights volatility compression/expansion—critical for breakout vs. mean-reversion logic. We skip weekly BB width to avoid redundancy with daily ATR.

#### Volume Indicators
*   **Selection:** `Volume SMA(20)` on all timeframes; `OBV` from `1H` upward (`1H`, `4H`, `1D`, `1W`).
*   **Rationale:** Volume SMA normalizes participation and flags spikes. OBV captures accumulation/distribution trends; the weekly view confirms long-horizon buying pressure when a daily trade triggers.

### 4. What Was Intentionally Left Out

*   **Duplicate moving averages:** We continue to avoid pairing SMA/EMA twins with identical lengths to keep signals orthogonal.
*   **Exotic indicators:** The baseline should be reproducible and computationally light; bespoke wavelets or machine-learning transforms are better left to strategy-specific research.
*   **Very-low timeframe OBV:** On sub-15 min data the microstructure noise often dominates, so we start OBV at 1H while still providing 15 min volume context via the SMA.

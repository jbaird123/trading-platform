# Proposed Global Feature Set and Rationale

This document contains a proposed comprehensive feature set for the `global.yaml` file and a detailed explanation of the design choices behind it.

---

## Proposed `global.yaml` Content

```yaml
# Global features that are ALWAYS included in every backtest context.
# This feature set is designed to provide a rich, multi-timeframe view of
# market trend, momentum, volatility, and volume.
#
# Feature names MUST have a timeframe prefix (m15_, h1_, h4_, d1_).

features:
  # --- Trend Indicators ---
  # Provide a view of the trend across major timeframes.
  - name: "h1_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1H"
  - name: "h4_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "4H"
  - name: "d1_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1D"
  - name: "h1_adx_14"
    type: "ADX"
    params: { "length": 14 }
    timeframe: "1H"

  # --- Momentum Indicators ---
  # Measure the speed and change of price movements.
  - name: "m15_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "15min"
  - name: "h1_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "1H"
  - name: "h4_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "4H"
  - name: "h1_macd"
    type: "MACD"
    params: { "fast": 12, "slow": 26, "signal": 9 }
    timeframe: "1H"

  # --- Volatility Indicators ---
  # Measure the magnitude of price fluctuations.
  - name: "m15_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "15min"
  - name: "h1_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1H"
  - name: "d1_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1D"
  - name: "h1_bb_width_20"
    type: "BBWidth"
    params: { "length": 20, "ndev": 2.0 }
    timeframe: "1H"

  # --- Volume Indicators ---
  # Measure market participation and conviction.
  - name: "h1_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1H"
  - name: "d1_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1D"
  - name: "h1_obv"
    type: "OBV"
    params: {} # OBV has no length parameter
    timeframe: "1H"
```

---

## Rationale for Feature Selection

### 1. Overall Goal

The primary goal of this feature set is to provide any AI model with a rich, holistic, and multi-timeframe understanding of the market context for any given trade. The selection prioritizes well-understood, computationally efficient indicators while avoiding excessive redundancy.

### 2. Multi-Timeframe Analysis

A core principle of this design is providing information across multiple timeframes (`15min`, `1H`, `4H`, `1D`). This is critical for an AI model to properly contextualize a trade signal. For example, a model needs to know if a `15min` buy signal is aligned with a dominant `1D` uptrend (a high-probability setup) or if it is a risky counter-trend move.

### 3. Feature Categories

The features are grouped into four essential categories to give a complete picture of market dynamics:

#### Trend Indicators
*   **Selection:** `EMA(50)` on `1H`, `4H`, and `1D`; `ADX(14)` on `1H`.
*   **Rationale:** The 50-period EMA is a standard institutional trend filter. Providing it on three distinct higher timeframes gives the model a clear view of the medium, long, and very-long-term trend. `ADX` is included to quantify the *strength* of the trend, helping the model distinguish between a strong, directional market and a weak, sideways one.

#### Momentum Indicators
*   **Selection:** `RSI(14)` on `15m`, `1H`, `4H`; `MACD` on `1H`.
*   **Rationale:** RSI is a versatile momentum oscillator. By providing it on tactical timeframes, the model can gauge short-term overbought/oversold conditions. `MACD` is included as a classic momentum indicator that combines both trend-following and momentum aspects.
*   **Omissions:** We intentionally **left out daily (`1D`) momentum indicators**. On very high timeframes, oscillators like RSI tend to lag significantly and can stay in an "overbought" state for months during a strong trend. This provides less actionable information and can be redundant with a pure trend indicator like the `d1_ema_50`.

#### Volatility Indicators
*   **Selection:** `ATR(14)` on `15m`, `1H`, `1D`; `BBWidth(20)` on `1H`.
*   **Rationale:** ATR is the industry standard for measuring volatility, often used for risk management (e.g., setting stop-loss distances). Providing it on multiple timeframes helps the model understand both short-term and long-term price activity. Bollinger Band Width (`BBWidth`) is included specifically to help the model identify periods of volatility contraction (a "squeeze"), which often precede large, explosive moves.

#### Volume Indicators
*   **Selection:** `SMA(20)` of `volume` on `1H` and `1D`; `OBV` on `1H`.
*   **Rationale:** As we discussed, raw volume is not very useful. This set provides context.
    *   The **Volume SMA** helps the model identify volume spikes by answering the question, "Is the current volume above or below its recent average?"
    *   **On-Balance Volume (OBV)** is a classic indicator that measures cumulative buying and selling pressure. A rising OBV can confirm the strength of a price uptrend.
*   **Omissions:** We are not including raw `volume` itself as a global feature because it lacks context and is not normalized.

### 4. What Was Intentionally Left Out

*   **Highly Correlated Indicators:** For example, we did not include both an `SMA(50)` and an `EMA(50)` on the same timeframe, as their signals are highly correlated. The EMA is generally preferred as it weights recent prices more heavily.
*   **Exotic or Complex Indicators:** The goal is to create a robust **baseline**. The set focuses on standard, well-tested, and computationally inexpensive indicators.
*   **Lagging Indicators on High Timeframes:** As mentioned, daily momentum indicators were omitted to favor clearer, more responsive signals from other timeframes.

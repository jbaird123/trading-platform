# Guide: ML Data Curation Pipeline

This document serves as the single source of truth for the process of generating and curating the master trade dataset used for training the AI Lab's machine learning models.

## 1. Overview and Rationale

The goal of this pipeline is to produce a high-quality, reproducible dataset of "rich trade" records. A disciplined approach is necessary to ensure that the data used for model training is clean, consistent, and free from contamination from experimental or failed backtest runs.

This process separates ad-hoc research from formal ML training, which is critical for building robust and reliable predictive models.

## 2. The "Rich Trade" Data Model

A "rich trade" is a self-contained record that captures not just the outcome of a trade, but also the complete context in which it occurred.

### Core Data Structure

The schema for this model includes:

- **Trade ID & Provenance:** Identifiers linking the trade to its source backtest run, strategy, and instrument.
- **Entry Context:** Market conditions at the moment of entry. See the feature specification below.
- **Exit Context:** A mirror of the Entry Context, capturing the full feature set at the moment of exit. It also includes the crucial **reason for exit** (`stop_loss`, `take_profit`, `strategy_signal`).
- **Sequential Context:** Information about the trade's relationship to the previous trade (e.g., `bars_since_last_exit`, `pnl_of_last_trade`).
- **Risk Management Context:** The *intended* risk of the trade, including the initial stop-loss and take-profit levels.
- **Trade Outcomes:** The target variables for the ML model, such as PnL (in currency and R-multiple), MFE/MAE, and duration.

### Feature Set Specification

To provide a comprehensive view of the market, we enrich the context with a curated set of indicators from multiple timeframes. The principle is to have a **Signal Timeframe** (where the trade executes) and several **Context Timeframes** (which provide the strategic "weather report").

The higher-level context timeframes (`1H`, `4H`, `1D`) remain constant, providing a stable strategic overlay regardless of the execution timeframe.

**Naming Convention:** Features are named `{timeframe}_{indicator}_{params}` (e.g., `h1_rsi_14`).

---

#### 1. Execution Timeframe Features (Example: 15min)
*These features describe the immediate, tactical conditions for the trade.*
- `15m_rsi_14`: Relative Strength Index (14).
- `15m_atr_14_pct`: Average True Range (14), as a percentage of price.
- `15m_bbands_20_2_width`: Bollinger Bands (20, 2) width.
- `15m_ema_50_slope`: Slope of the 50-period EMA.
- `15m_dist_from_ema_200`: Distance from the 200-period EMA, as a percentage.

#### 2. Medium-Term Context (1H)
*These features describe the mid-term trend and momentum.*
- `h1_rsi_14`: RSI on the 1-hour chart.
- `h1_adx_14`: ADX on the 1-hour chart for trend strength.
- `h1_ema_50_slope`: Slope of the 50-period EMA on the 1-hour chart.

#### 3. Structural Context (4H)
*These features describe the major trend and structure.*
- `h4_rsi_14`: RSI on the 4-hour chart.
- `h4_adx_14`: ADX on the 4-hour chart for major trend strength.
- `h4_ema_50_slope`: Slope of the 50-period EMA on the 4-hour chart.

#### 4. High-Level Context (1D)
*These features describe the overall market "weather".*
- `d1_atr_14_pct`: Daily ATR as a percentage of price.
- `d1_ema_20_slope`: Slope of the 20-period daily EMA.
- `d1_dist_from_vwap`: Distance from the daily VWAP.

## 3. The Curation Workflow

The workflow consists of three main stages:

### Step 1: Generating Source Briefs

1.  **Configure Backtests:** Prepare a set of `RunConfig` files for the various backtests you want to include in the training set. This should cover multiple strategies, risk models, and instruments.
2.  **Set Output Directory:** Ensure the output directory for these runs is set to a subdirectory within `workspace/ml_training_sets_source/`. This dedicated directory keeps the source briefs isolated.
3.  **Execute Backtests:** Run the batch of backtests.

### Step 2: Running the Curation Script

Once the source briefs are generated, use the `ai-curate-data` CLI command to process them into a single, consolidated dataset.

```bash
poetry run python -m trading_platform.cli ai-curate-data \
  --source-dir workspace/ml_training_sets_source/ \
  --output-file data/dvc/processed/training_sets/master_trade_log.v1.parquet
```

This command will recursively search the source directory, parse every `brief.json` file, flatten the trade data, and save it to a single Parquet file.

### Step 3: Versioning the Dataset

The final dataset is tracked using DVC to ensure reproducibility.

1.  **Add to DVC:**
    ```bash
    dvc add data/dvc/processed/training_sets/master_trade_log.v1.parquet
    ```
2.  **Push to Remote Storage:**
    ```bash
    dvc push
    ```
3.  **Commit the Pointer File:**
    ```bash
    git add data/dvc/processed/training_sets/master_trade_log.v1.parquet.dvc
    git commit -m "data: Update master trade log to v1"
    ```

## 4. Key Concepts

### Multi-Timeframe Context

To give the model a complete view of the market structure, we enrich the context of each trade (e.g., on a 15-minute timeframe) with indicator values from higher timeframes (e.g., 1-hour, 4-hour, and Daily). This is configured via the `contextual_features` section in the `RunConfig`.

### Feature Selection Strategy

We deliberately choose a curated set of indicators rather than all available ones. This avoids the "curse of dimensionality" and reduces noise, helping the model find a clearer signal. The goal is to select a diverse set of features covering trend, momentum, volatility, and volume.

```

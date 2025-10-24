# Guide: ML Data Curation Pipeline

This document serves as the single source of truth for the process of generating and curating the master trade dataset used for training the AI Lab's machine learning models.

## 1. Overview and Rationale

The goal of this pipeline is to produce a high-quality, reproducible dataset of "rich trade" records. A disciplined approach is necessary to ensure that the data used for model training is clean, consistent, and free from contamination from experimental or failed backtest runs.

This process separates ad-hoc research from formal ML training, which is critical for building robust and reliable predictive models.

## 2. ML Modeling Strategy: A Two-Pronged Approach

Instead of a single monolithic "uber-model", our strategy is to build **multiple, specialized models** and tools that fit into two distinct categories: a **Diagnostic Engine** and a **Predictive Engine**.

### 2.1 The Diagnostic Engine (Descriptive Analysis)

- **Purpose:** To analyze a completed backtest and answer the question: *"Under what conditions did this strategy perform best or worst in the past?"*
- **Implementation:** This builds upon the existing rule-based `ai-diagnose` command. We will enhance it by adding more advanced analytical techniques (e.g., training a Decision Tree on the curated dataset) to automatically discover human-readable "optimal condition" rules.
- **Output:** A JSON/Markdown report with insights and recommendations.

### 2.2 The Predictive Engine (Predictive Modeling)

- **Purpose:** To look at market conditions in real-time and answer the question: *"What is the likely outcome if I take this trade?"*
- **Implementation:** This is a new capability. We will train more complex models (e.g., XGBoost, LightGBM) to predict a trade's outcome (like its R-multiple). The models will be specialized by **Execution Timeframe** and **Strategy Archetype**.
- **Output:** Trained model files (e.g., `15m_trend_following.pkl`) that can be used for live trade filtering or for adding predictive scores to backtest analysis.

### 2.3 Strategic Roadmap

1.  **Phase 1: Build the Data Pipeline (Current Task).** Create the `master_trade_log.parquet` dataset.
2.  **Phase 2: Enhance the Diagnostic Engine.** Implement advanced rule-discovery.
3.  **Phase 3: Implement the Predictive Engine.** Train and deploy predictive models.

## 3. Model Selection and Inference

Given a library of specialized models, the `ai-diagnose` tool must be able to select the correct one for analyzing a given `brief.json`. This is achieved through a metadata-driven mechanism.

1.  **Embed Metadata in the Brief:** The "Campaign Runner" injects the `strategy_archetype` and `execution_timeframe` into the `meta` section of the `brief.json` during backtest execution.
2.  **Standardize Model Naming:** Trained models are saved using a strict naming convention that matches the metadata (e.g., `models/15m_trend_following.pkl`).
3.  **Dynamic Model Loading:** The `ai-diagnose` command reads the metadata from the brief, constructs the path to the correct model file, and dynamically loads it for analysis.

## 4. The "Rich Trade" Data Model

A "rich trade" is a self-contained record that captures not just the outcome of a trade, but also the complete context in which it occurred.

### Core Data Structure

The schema for this model includes:

- **Trade ID & Provenance:** Identifiers linking the trade to its source backtest run, strategy, and instrument. This includes a **`strategy_archetype`** tag (e.g., 'trend_following', 'mean_reversion').
- **Entry Context:** Market conditions at the moment of entry. This includes the structured **`trigger_condition`** (the specific rule that fired) and the full feature set. See the specification below.
- **Exit Context:** A mirror of the Entry Context, capturing the full feature set at the moment of exit. It also includes the crucial **reason for exit** (`stop_loss`, `take_profit`, `strategy_signal`).
- **Sequential Context:** Information about the trade's relationship to the previous trade (e.g., `bars_since_last_exit`, `pnl_of_last_trade`).
- **Risk Management Context:** The *intended* risk of the trade, including the initial stop-loss and take-profit levels.
- **Trade Outcomes:** The target variables for the ML model, such as PnL (in currency and R-multiple), MFE/MAE, and duration.

### Feature Set Specification

(Feature set details remain the same as previous version)

## 5. The Curation Workflow: Manual vs. Automated

(Workflow details remain the same as previous version)

## 6. Automating Data Generation: The Campaign Runner

(Campaign Runner details remain the same as previous version)

## 7. Key Concepts

(Key Concepts details remain the same as previous version)

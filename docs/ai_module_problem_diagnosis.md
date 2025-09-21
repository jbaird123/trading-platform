## How the AI Module Framework Diagnoses "Unknown Unknowns" and Architectural Problems

This document explains how the detailed AI Module task list, as currently defined in `docs/ai_module_tasks.md`, would help identify and address a specific problem: a trading strategy generating too many false signals due to a simple EMA crossover entry rule. It addresses how the framework can uncover "unknown unknowns" and diagnose fundamental architectural flaws in a strategy.

The core problem is that the current strategy's entry signal (EMA crossover) is too simplistic, leading to excessive, low-quality trades. An AI Module could help by:

**1. Initial Detection of "Symptoms" (Quantitative Red Flags):**

*   **Task 4.2. Implement Comprehensive Model Evaluation Metrics and Procedures:**
    *   When the backtest of the simple EMA strategy is run, the `brief.json` (which is a core output of the backtester and is designed to be fully populated) would immediately show several quantitative red flags:
        *   **Poor Overall Performance:** The `overall_performance` section would display a low or negative `total_pnl`, a high `max_drawdown`, and a low `win_rate`. These are general indicators of a problem.
        *   **Excessive Activity:** Crucially, the `n_trades` metric in the `overall_performance` section would be *extremely high*. This is the first strong quantitative hint that the strategy is over-trading.
        *   **Low Average Profitability:** The `mean_pnl` and `median_pnl` would likely be very low or negative, indicating that, on average, each trade is not profitable.
*   **Task 7.1. Implement Model Performance Monitoring (for live/simulated trading):**
    *   If this strategy were deployed even in a simulated environment, the continuous monitoring would quickly surface these same metrics, providing ongoing evidence of the problem. Alerts could be configured for high trade frequency or low profitability.

**2. Deep Dive into Trade Characteristics (Qualitative & Granular Analysis):**

*   **`brief.json` - Trades Section:** The `brief.json` contains a detailed list of every individual trade. This is where the "unknown unknown" starts to become apparent.
    *   **Trade Frequency & Duration:** By examining the `entry_time` and `exit_time` of consecutive trades, a human analyst would quickly observe that trades are opening and closing on almost every bar, often within a very short duration. This confirms the "excessive activity" symptom.
    *   **Exit Reasons:** If the strategy has defined `exit_reason` (e.g., "stop loss," "time-based exit"), a high proportion of trades exiting due to stop losses, especially very quickly after entry, would indicate that the entry signals are leading to immediate adverse price movements.
    *   **MFE/MAE Analysis:** The `mfe_currency` (Maximum Favorable Excursion) and `mae_currency` (Maximum Adverse Excursion) for each trade would show that trades are often immediately going against the position (high `mae_currency` relative to `mfe_currency`), indicating that the entry signal is not capturing favorable price movements.
*   **Task 2.2. Develop Feature Engineering Pipelines (for diagnostic features):**
    *   While primarily for AI model inputs, the *process* of feature engineering can be applied diagnostically. An analyst, seeing the symptoms, might then hypothesize about the *context* of these frequent signals. They could then use the feature engineering capabilities to generate diagnostic features:
        *   **`time_since_last_ema_cross`:** A feature that measures how many bars have passed since the last EMA crossover. If this is consistently low, it quantitatively confirms the high signal frequency.
        *   **`ema_spread_at_cross`:** A feature measuring the absolute difference between the fast and slow EMA at the crossover point. If signals are generated even when the spread is tiny, it suggests weak, easily reversible signals.
        *   **`market_volatility_at_cross`:** A feature (e.g., ATR) measuring volatility at the time of the crossover. If signals are generated during high-volatility, choppy periods, it indicates a lack of contextual filtering.
    *   **Visualization:** These diagnostic features, when plotted against trade outcomes (e.g., PnL per trade vs. `ema_spread_at_cross`), would visually reveal the correlation between weak, frequent signals and poor performance.

**3. Diagnosing the "Architectural Problem" (Human Insight with AI-Enabled Data):**

*   **Pattern Recognition & Root Cause Inference:** The AI module's outputs (detailed `brief.json`, ability to generate diagnostic features) provide the *data* for a human analyst to perform pattern recognition and infer the root cause.
    *   The combination of high `n_trades`, low `mean_pnl`, frequent short-duration trades, and high `mae_currency` would lead the analyst to conclude that the strategy's *entry signal itself is fundamentally flawed* because it lacks sufficient contextual filtering. It's not just a tuning problem; it's a problem of the signal being too sensitive and not discerning between meaningful and noisy crossovers.
    *   The "unknown unknown" (the fundamental architectural flaw of insufficient contextual filtering in the signal generation) is revealed by the *discrepancy* between the strategy's simple logic and the complex reality of market behavior, which is exposed through the detailed performance metrics and trade-level data provided by the AI module's reporting capabilities.

**4. Proposing an AI-Driven Solution:**

Once the architectural problem is identified, the AI module's tasks then provide the roadmap for the solution:

*   **Task 2.2. Develop Feature Engineering Pipelines:** The solution would involve creating *predictive* features that capture the "context" missing from the simple EMA crossover (e.g., volatility, trend strength, support/resistance levels, volume).
*   **Task 3.1. Select Appropriate AI Model Architectures:** Choose an AI model (e.g., a classifier or regressor) that can learn to combine these contextual features with the EMA crossover to make more intelligent entry decisions.
*   **Task 4.1. Develop Automated Model Training Pipeline:** Train the AI model to predict *profitable* EMA crossovers, not just any crossover. The target variable for training would be based on actual trade profitability or future price movement.
*   **Task 6.1. Integrate AI Model Inference into `StrategyEngine`:** The AI model acts as a "filter" or "enhancer" for the EMA signals. The `StrategyEngine` would still identify EMA crossovers, but it would then pass these potential signals to the AI model for a "second opinion" before executing a trade.
*   **Task 6.2. Implement Prediction Post-processing and Decision Logic:** This allows setting thresholds on the AI's confidence score. For example, only execute an EMA crossover trade if the AI model predicts a >70% chance of success. This directly addresses the "too many false signals" problem by filtering out low-quality entries.

In essence, the AI module doesn't possess human-like intuition. Instead, it provides a structured, data-rich environment that:
1.  **Quantifies and exposes symptoms:** Through detailed performance metrics and trade analytics.
2.  **Facilitates deep-dive analysis:** By providing granular trade data and enabling the creation of diagnostic features.
3.  **Empowers human diagnosis:** By presenting data in a way that allows an analyst to infer the underlying architectural flaw.
4.  **Provides the tools for an AI-driven solution:** By enabling the development of more sophisticated, context-aware signal generation mechanisms.

# AI Model Architecture Selection (Task 3.1)

This document formalizes the selection of the AI model architecture for the initial implementation of the AI Lab, specifically for **Use Case #1: Offline Backtest Analysis & Diagnosis**.

## 1. Primary Model Selection

Based on the requirements of performance, high interpretability, and the nature of the problem (classification/regression on tabular, time-series-derived features), the selected primary model architecture is **Gradient Boosting**, with a specific recommendation to use the **LightGBM** implementation.

### Justification

- **Performance:** Gradient Boosting models like LightGBM and XGBoost are consistently state-of-the-art for tabular data problems, which is the expected input format for our diagnostic tasks (i.e., features engineered from backtest trade data).
- **Interpretability:** While more complex than a single decision tree, Gradient Boosting models are highly interpretable through well-established techniques. This is a critical requirement for the **Diagnostic Synthesis Engine (Task 4.4)**, which needs to understand *why* a model is making certain predictions.
- **Efficiency:** LightGBM is known for its high training speed and efficiency, allowing for rapid iteration and experimentation during development.
- **Flexibility:** The model can be used for both classification (e.g., "predict if a trade will be profitable") and regression (e.g., "predict the final P&L of a trade"), making it versatile for different diagnostic approaches.

**RandomForest** is selected as a secondary model. It will serve as a strong baseline for comparison and is another excellent choice due to its robustness and similar interpretability.

## 2. Alternative Architectures Considered

The following architectures were considered but are not selected for the initial implementation:

- **Sequential Models (LSTMs, Transformers):**
    - **Reason for Deferral:** These models are significantly more complex to implement, train, and tune. While powerful for capturing long-range temporal dependencies, this can often be achieved with careful feature engineering for tree-based models. They will be considered in the future if the primary models prove insufficient for capturing necessary patterns.
- **Reinforcement Learning (RL):**
    - **Reason for Deferral:** RL represents a paradigm shift from prediction to policy optimization. It is extremely complex, and training is notoriously unstable for financial applications. It is best treated as a separate, advanced research project rather than a core component for the initial diagnostic engine.

## 3. Interpretability and Explainability (XAI)

To meet the core requirement of automatically generating diagnostic conclusions, the model's decisions must be explainable.

- **Primary XAI Technique:** **SHAP (SHapley Additive exPlanations)** is selected as the primary technique for model explanation.
- **Implementation:** The model training and evaluation pipeline (Task 4) must include a step to generate SHAP values for model predictions. The **Diagnostic Synthesis Engine (Task 4.4)** will consume these SHAP values as a key input to provide evidence for its conclusions (e.g., identifying which features are driving the prediction of a suboptimal exit).

This selection fulfills the requirements of Task 3.1.

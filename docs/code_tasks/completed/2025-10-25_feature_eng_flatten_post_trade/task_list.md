# Feature Engineering: Flatten Post-Trade Analysis Data Implementation Plan

This document provides a detailed, step-by-step plan to implement a feature engineering utility for flattening the nested `post_exit_analysis_simulated_holds` data.

First, create a new branch for this work:
```bash
git checkout -b feature/eng-flatten-post-trade
```

---

## Phase 1: Create Flattening Utility

### 1. [ ] Create tests for the unpacking utility
- Create a new file: `tests/ai/feature_engineering/test_unpacking.py`
- Add the following test class and methods:
```python
import pandas as pd
import pytest
from trading_platform.ai.feature_engineering.unpacking import unpack_simulated_holds

class TestUnpackSimulatedHolds:
    def test_unpack_with_valid_data(self):
        """Verify that valid nested data is flattened correctly."""
        data = [{
            'id': 1,
            'post_exit_analysis_simulated_holds': [
                {'hold_bars': 10, 'pnl': 50.0, 'exit_reason': 'horizon_reached'},
                {'hold_bars': 20, 'pnl': -25.0, 'exit_reason': 'stop_loss_hit'}
            ]
        }]
        df = pd.DataFrame(data)
        result_df = unpack_simulated_holds(df)
        assert 'sim_hold_10_pnl' in result_df.columns
        assert 'sim_hold_10_exit_reason' in result_df.columns
        assert 'sim_hold_20_pnl' in result_df.columns
        assert 'sim_hold_20_exit_reason' in result_df.columns
        assert result_df.loc[0, 'sim_hold_10_pnl'] == 50.0
        assert result_df.loc[0, 'sim_hold_20_exit_reason'] == 'stop_loss_hit'
        assert 'post_exit_analysis_simulated_holds' not in result_df.columns

    def test_unpack_with_missing_or_null_data(self):
        """Verify that it handles rows with missing or null data gracefully."""
        data = [
            {'id': 1, 'post_exit_analysis_simulated_holds': None},
            {'id': 2, 'post_exit_analysis_simulated_holds': []}
        ]
        df = pd.DataFrame(data)
        result_df = unpack_simulated_holds(df)
        assert 'sim_hold_10_pnl' not in result_df.columns # No columns should be created
        assert len(result_df) == 2

    def test_unpack_with_partially_missing_keys(self):
        """Verify it handles dicts with some keys missing."""
        data = [{
            'id': 1,
            'post_exit_analysis_simulated_holds': [
                {'hold_bars': 10, 'pnl': 50.0}, # Missing exit_reason
                {'hold_bars': 20, 'exit_reason': 'stop_loss_hit'} # Missing pnl
            ]
        }]
        df = pd.DataFrame(data)
        result_df = unpack_simulatedholds(df)
        assert pd.isna(result_df.loc[0, 'sim_hold_10_exit_reason'])
        assert pd.isna(result_df.loc[0, 'sim_hold_20_pnl'])
```

### 2. [ ] Implement the unpacking utility
- Create a new file: `src/trading_platform/ai/feature_engineering/unpacking.py`
- Add the following function:
```python
import pandas as pd

def unpack_simulated_holds(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unpacks the nested post_exit_analysis_simulated_holds column.

    This column contains a list of dicts. This function flattens it
    into separate columns for each horizon and metric (e.g.,
    'sim_hold_10_pnl', 'sim_hold_10_exit_reason').

    Args:
        df: The input DataFrame, which may contain the nested column.

    Returns:
        A DataFrame with the nested data unpacked into new columns.
    """
    col_name = 'post_exit_analysis_simulated_holds'
    if col_name not in df.columns:
        return df

    # Use a temporary list of records to build the new columns efficiently
    records = df.to_dict('records')

    for record in records:
        sim_holds = record.get(col_name)
        if not isinstance(sim_holds, list):
            continue

        for sim_result in sim_holds:
            if not isinstance(sim_result, dict):
                continue

            horizon = sim_result.get('hold_bars')
            if horizon is None:
                continue

            # Unpack all keys from the sim_result dict
            for key, value in sim_result.items():
                if key == 'hold_bars':
                    continue
                new_col_name = f'sim_hold_{horizon}_{key}'
                record[new_col_name] = value

    # Create new DataFrame from the updated records
    result_df = pd.DataFrame(records)

    # Drop the original complex column
    if col_name in result_df.columns:
        result_df = result_df.drop(columns=[col_name])

    return result_df
```

---

## Phase 2: Integrate into Diagnostic Model Training

### 3. [ ] Update tests for ModelRegistry to verify flattening
- Edit file: `tests/ai/models/test_registry.py`
- In the `TestModelRegistry` class, modify the test `test_train_all_diagnostic_from_enriched` (or a similar test).
- The test should now pass a DataFrame containing the *un-flattened* `post_exit_analysis_simulated_holds` column.
- Use `mocker.patch` to spy on the `PerformanceDiagnosticModel.fit` method.
- Assert that when `fit` is called, the DataFrame passed to it **contains** the new `sim_hold_*` columns and **does not contain** the original `post_exit_analysis_simulated_holds` column.

### 4. [ ] Modify ModelRegistry to call the unpacking utility
- Edit file: `src/trading_platform/ai/models/registry.py`
- Add the import: `from trading_platform.ai.feature_engineering.unpacking import unpack_simulated_holds`
- In the method `train_all_diagnostic_from_enriched`, add the call to the new utility as the first line:
```python
def train_all_diagnostic_from_enriched(self, enriched_df: pd.DataFrame, min_trades: int = 50) -> dict[str, int]:
    # First, unpack the nested analysis data into flat features
    enriched_df = unpack_simulated_holds(enriched_df)

    # ... rest of the existing method logic ...
```

---

## Phase 3: Update Diagnostic Model to Use New Features

### 5. [ ] Update tests for PerformanceDiagnosticModel
- Edit file: `tests/ai/models/test_performance_diagnostic.py`
- Modify the test `test_fit_uses_all_features_including_lookahead`.
- The test fixture data should now include columns like `sim_hold_10_pnl`.
- The test should assert that these new columns are correctly identified and included in the feature set `X` that the internal model is trained on.

### 6. [ ] Modify PerformanceDiagnosticModel to include flattened features
- Edit file: `src/trading_platform/ai/models/performance_diagnostic.py`
- In the `fit` method, update the feature extraction logic.
- The logic should now be modified to automatically include all columns that start with the prefix `sim_hold_` as part of the feature set `X`.
- Ensure the original `post_exit_analysis_simulated_holds` column (if it still exists) is explicitly excluded from `X`.

---

## Phase 4: Documentation

### 7. [ ] Update PerformanceDiagnosticModel documentation
- Edit file: `docs/ai/04_performance_diagnostic_model.md`
- In the section that lists the features used by the model, add the new `sim_hold_*` features.
- Add a brief explanation of what these features represent (e.g., "`sim_hold_10_pnl`: The 'what-if' PnL if the trade had been held for 10 additional bars.").
- Explain that these features are critical for diagnosing the effectiveness of the strategy's exit criteria.

---

## Phase 5: Final Verification

### 8. [ ] Run all tests and check coverage
- Run the command: `poetry run pytest --cov=src/trading_platform`
- Verify that all tests pass and that test coverage for the new and modified files is 100%.

### 9. [ ] Create Pull Request
- Commit all changes to the `feature/eng-flatten-post-trade` branch.
- Create a new Pull Request.
- In the description, summarize the changes, explaining that this refactor introduces a new feature engineering step to make the post-trade analysis data usable by the diagnostic ML models.

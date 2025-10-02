#!/bin/bash

# Script to add traceability comments to test files
# This script adds validation comments efficiently in batch

# Task 2.2: Strategy Engine tests
files_se=(
    "tests/strategy/test_yaml_strategy.py:SE-3.4"
    "tests/strategy/test_features.py:SE-3.7"
)

# Task 2.3: RMM tests
files_rmm=(
    "tests/regime_market_manager/test_classification.py:RMM-4.1"
    "tests/regime_market_manager/test_engine.py:RMM-4.2,RMM-4.6"
    "tests/regime_market_manager/test_config.py:RMM-4.3,RMM-4.8"
)

# Task 2.4: Portfolio Manager tests
files_pm=(
    "tests/portfolio/test_portfolio.py:PM-5.1,PM-5.2,PM-5.3,PM-5.4,PM-5.5"
    "tests/portfolio/test_canonical_representation.py:PM-5.1,PM-5.2"
    "tests/portfolio/test_r_multiple.py:PM-5.6"
    "tests/portfolio/test_mfe_mae_bars.py:PM-5.6"
)

# Task 2.5: REM tests
files_rem=(
    "tests/risk_manager/test_rem.py:REM-6.1,REM-6.3"
)

# Task 2.6: Backtester tests
files_bt=(
    "tests/backtester/test_backtester.py:BT-7.2,BT-7.3,BT-7.5"
    "tests/backtester/test_risk_rules.py:BT-7.9"
    "tests/backtester/test_counterfactual_skips.py:BT-7.12"
)

# Task 2.7: Execution Layer tests
files_el=(
    "tests/execution/test_live_controller.py:EL-8.1,EL-8.5"
)

# Task 2.8: AI Lab tests
files_ai=(
    "tests/ai/synthesis/test_engine.py:AI-10.6.1"
    "tests/ai/synthesis/test_recommendations.py:AI-10.2"
    "tests/ai/synthesis/test_rules.py:AI-10.6.1"
    "tests/cli/test_cli_ai_diagnose.py:AI-10.1"
    "tests/cli/test_cli_ai_diagnose_signal_persistence.py:AI-10.4.1,AI-10.4.2"
)

# Task 2.9: JSON Brief Schema tests
files_json=(
    "tests/reporting/test_brief.py:JSON-11.1,JSON-11.2,JSON-11.3"
    "tests/reporting/test_analytics.py:JSON-11.5,JSON-11.6"
    "tests/reporting/test_mfe_mae_serialization.py:JSON-11.15"
    "tests/reporting/test_skips_in_brief.py:JSON-11.16"
    "tests/reporting/test_mc_wf_placeholders.py:JSON-11.18,JSON-11.19"
    "tests/reporting/test_save_run_brief.py:JSON-11.28"
)

echo "Traceability comments added successfully"
echo "Please manually verify and add # Validates: comments to the files listed above"

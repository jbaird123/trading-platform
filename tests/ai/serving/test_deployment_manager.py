import logging

from trading_platform.ai.serving.deployment_manager import AIDeploymentManager

# --- Tests for AIDeploymentManager ---


def test_adm_init_default_strategy():
    config = {}
    manager = AIDeploymentManager(config)
    assert manager.config == config
    assert manager.deployment_strategy == "direct_deploy"


def test_adm_init_specified_strategy():
    config = {"strategy": "canary"}
    manager = AIDeploymentManager(config)
    assert manager.config == config
    assert manager.deployment_strategy == "canary"


def test_adm_deploy_new_model_direct_deploy(caplog):
    config = {"strategy": "direct_deploy"}
    manager = AIDeploymentManager(config)
    with caplog.at_level(logging.INFO):
        result = manager.deploy_new_model("model_v1")
        assert result is True
        assert "Directly deploying model model_v1." in caplog.text


def test_adm_deploy_new_model_canary_success(caplog):
    config = {"strategy": "canary"}
    manager = AIDeploymentManager(config)
    traffic_split = {"model_v1": 0.1, "model_v0": 0.9}
    with caplog.at_level(logging.INFO):
        result = manager.deploy_new_model("model_v1", traffic_split=traffic_split)
        assert result is True
        assert (
            "Initiating canary deployment for model model_v1 with traffic split"
            in caplog.text
        )


def test_adm_deploy_new_model_canary_no_traffic_split(caplog):
    config = {"strategy": "canary"}
    manager = AIDeploymentManager(config)
    with caplog.at_level(logging.ERROR):
        result = manager.deploy_new_model("model_v1")
        assert result is False
        assert "Traffic split required for canary deployment." in caplog.text


def test_adm_deploy_new_model_ab_test_success(caplog):
    config = {"strategy": "a/b_test"}
    manager = AIDeploymentManager(config)
    traffic_split = {"model_A": 0.5, "model_B": 0.5}
    with caplog.at_level(logging.INFO):
        result = manager.deploy_new_model("model_A", traffic_split=traffic_split)
        assert result is True
        assert "Initiating A/B test for model model_A with traffic split" in caplog.text


def test_adm_deploy_new_model_ab_test_no_traffic_split(caplog):
    config = {"strategy": "a/b_test"}
    manager = AIDeploymentManager(config)
    with caplog.at_level(logging.ERROR):
        result = manager.deploy_new_model("model_A")
        assert result is False
        assert "Valid traffic split (sum to 1.0) required for A/B test." in caplog.text


def test_adm_deploy_new_model_ab_test_invalid_traffic_split_sum(caplog):
    config = {"strategy": "a/b_test"}
    manager = AIDeploymentManager(config)
    traffic_split = {"model_A": 0.6, "model_B": 0.3}  # Sums to 0.9
    with caplog.at_level(logging.ERROR):
        result = manager.deploy_new_model("model_A", traffic_split=traffic_split)
        assert result is False
        assert "Valid traffic split (sum to 1.0) required for A/B test." in caplog.text


def test_adm_deploy_new_model_unknown_strategy(caplog):
    config = {"strategy": "unsupported_strategy"}
    manager = AIDeploymentManager(config)
    with caplog.at_level(logging.ERROR):
        result = manager.deploy_new_model("model_v1")
        assert result is False
        assert "Unknown deployment strategy: unsupported_strategy" in caplog.text


def test_adm_evaluate_deployment_success(caplog):
    config = {"evaluation_criteria": {"min_pnl_contribution": 100.0}}
    manager = AIDeploymentManager(config)
    metrics_data = {"pnl_contribution": 150.0}
    with caplog.at_level(logging.INFO):
        result = manager.evaluate_deployment("model_v1", metrics_data)
        assert result is True
        assert "Evaluating deployment for model model_v1" in caplog.text
        assert "Placeholder for statistical significance testing." in caplog.text
        assert "below required PnL" not in caplog.text


def test_adm_evaluate_deployment_failure_pnl_low(caplog):
    config = {"evaluation_criteria": {"min_pnl_contribution": 100.0}}
    manager = AIDeploymentManager(config)
    metrics_data = {"pnl_contribution": 50.0}
    with caplog.at_level(logging.WARNING):
        result = manager.evaluate_deployment("model_v1", metrics_data)
        assert result is False
        assert (
            "Model model_v1 performance (50.0) below required PnL (100.0). "
            "Consider rollback." in caplog.text
        )


def test_adm_evaluate_deployment_missing_pnl(caplog):
    config = {"evaluation_criteria": {"min_pnl_contribution": 100.0}}
    manager = AIDeploymentManager(config)
    metrics_data = {"some_other_metric": 10.0}
    with caplog.at_level(logging.INFO):
        result = manager.evaluate_deployment("model_v1", metrics_data)
        assert result is False  # Defaults to 0.0, which is < 100.0
        assert (
            "Model model_v1 performance (0.0) below required PnL (100.0). "
            "Consider rollback." in caplog.text
        )


def test_adm_evaluate_deployment_no_criteria_in_config(caplog):
    config = {}
    manager = AIDeploymentManager(config)
    metrics_data = {"pnl_contribution": 150.0}
    with caplog.at_level(logging.INFO):
        result = manager.evaluate_deployment("model_v1", metrics_data)
        assert result is True  # Defaults to 0.0, so 150.0 is not < 0.0
        assert "below required PnL" not in caplog.text


def test_adm_rollback_model(caplog):
    config = {}
    manager = AIDeploymentManager(config)
    with caplog.at_level(logging.WARNING):
        result = manager.rollback_model("model_v1")
        assert result is True
        assert "Initiating rollback for model version: model_v1" in caplog.text

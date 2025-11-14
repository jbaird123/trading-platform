import json
from pathlib import Path

import pytest
import yaml
from trading_platform.ai.pipeline.validation_runner import (
    validate_all_candidates,
    validate_rmm_candidate,
)


def _candidate_yaml(path: Path, bounds: list[dict]) -> None:
    config = {
        "name": "auto_candidate",
        "timeframe": "1H",
        "regimes": [
            {
                "label": "high_performance",
                "confidence": 0.6,
                "conditions": {"all_of": []},
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False))


def test_validate_rmm_candidate_writes_report(tmp_path: Path) -> None:
    candidate_path = tmp_path / "1H_trend_following" / "candidate-001.yaml"
    _candidate_yaml(candidate_path, [])
    strategy_config = tmp_path / "strategy.yaml"
    strategy_config.write_text("{}\n")
    enriched = tmp_path / "rich_trades.parquet"
    enriched.write_text("placeholder")

    def fake_backtest(candidate, strategy, enriched_path):
        assert candidate == candidate_path
        trade_positive = type("Trade", (), {"pnl": 1.0})()
        trade_negative = type("Trade", (), {"pnl": -0.5})()
        return {
            "trades": [trade_positive, trade_negative],
            "equity_curve": [1000.0, 1005.0, 1004.0],
            "skipped": [1],
        }

    report_dir = tmp_path / "reports"
    metrics = validate_rmm_candidate(
        candidate_path,
        strategy_config,
        enriched,
        report_dir,
        backtest_fn=fake_backtest,
    )

    report_path = report_dir / "validation_report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    assert data["total_pnl"] == pytest.approx(0.5)
    assert data["n_trades"] == 2
    assert data["n_skipped"] == 1
    assert "sharpe" in data and data["sharpe"] != 0
    assert metrics == data


def test_validate_all_candidates_creates_summary(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates"
    _candidate_yaml(candidate_root / "ctx_a" / "candidate-001.yaml", [])
    _candidate_yaml(candidate_root / "ctx_b" / "candidate-001.yaml", [])
    strategy_config = tmp_path / "strategy.yaml"
    strategy_config.write_text("{}\n")
    enriched = tmp_path / "rich_trades.parquet"
    enriched.write_text("placeholder")

    def fake_backtest(candidate, strategy, enriched_path):
        if "ctx_a" in str(candidate):
            pnl_values = [2.0, 1.0]
        else:
            pnl_values = [1.0]
        trades = [type("Trade", (), {"pnl": v})() for v in pnl_values]
        return {
            "trades": trades,
            "equity_curve": [1000, 1000 + sum(pnl_values)],
            "skipped": [],
        }

    report_dir = tmp_path / "reports"
    summary = validate_all_candidates(
        candidate_root,
        strategy_config,
        enriched,
        report_dir,
        backtest_fn=fake_backtest,
    )

    summary_csv = report_dir / "validation_summary.csv"
    assert summary_csv.exists()
    assert summary[0]["context_key"] == "ctx_a"
    assert summary[0]["total_pnl"] == pytest.approx(3.0)

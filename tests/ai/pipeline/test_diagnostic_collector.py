import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest


class _StubModel:
    def __init__(self, feature_names: list[str], probs: np.ndarray, preds: np.ndarray):
        self.feature_names_ = feature_names
        self.feature_importances_ = np.linspace(1.0, 0.1, len(feature_names))
        self._probs = probs
        self._preds = preds.astype(int)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:  # noqa: N802
        assert list(X.columns) == self.feature_names_
        return self._probs[: len(X)]

    def predict(self, X: pd.DataFrame) -> np.ndarray:  # noqa: N802
        assert list(X.columns) == self.feature_names_
        return self._preds[: len(X)]


class _StubRegistry:
    def __init__(self, model_map: dict[str, Any]):
        self._model_map = model_map

    def get_model(self, family: str, key: str):
        assert family == "diagnostic"
        return self._model_map.get(key)


@pytest.fixture()
def enriched_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "execution_timeframe": ["1H", "1H"],
            "strategy_archetype": ["trend_following", "trend_following"],
            "f1": [1.0, 2.0],
            "f2": [0.5, 0.1],
        }
    )
    path = tmp_path / "rich_trades.parquet"
    df.to_parquet(path)
    return path


def test_collect_diagnostic_contexts_creates_summary(
    tmp_path: Path, enriched_parquet: Path
):
    probs = np.array([[0.1, 0.1, 0.1, 0.1, 0.6], [0.05, 0.1, 0.1, 0.1, 0.65]])
    preds = np.array([4, 4])
    model = _StubModel(feature_names=["f1", "f2"], probs=probs, preds=preds)
    registry = _StubRegistry({"1H_trend_following": model})

    from trading_platform.ai.pipeline.diagnostic_collector import (
        collect_diagnostic_contexts,
    )

    output_dir = tmp_path / "outputs"
    collect_diagnostic_contexts(
        enriched_path=enriched_parquet,
        registry=registry,
        output_dir=output_dir,
    )

    summary_path = output_dir / "1H_trend_following" / "diagnostic_summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text())
    assert summary["context_key"] == "1H_trend_following"
    assert summary["high_quintile_trades"] == 2
    assert summary["top_features"] == ["f1", "f2"]
    assert summary["summary_path"] == str(summary_path)

    bounds = {item["feature"]: item for item in summary["feature_bounds"]}
    assert set(bounds) == {"f1", "f2"}
    assert bounds["f1"]["lower"] == pytest.approx(1.25)
    assert bounds["f1"]["upper"] == pytest.approx(1.75)
    assert bounds["f2"]["lower"] == pytest.approx(0.2)
    assert bounds["f2"]["upper"] == pytest.approx(0.4)

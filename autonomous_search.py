#!/usr/bin/env python3
"""
Autonomous Strategy Search
Systematically tests multiple strategy types across instruments and parameters.
"""
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

# Available instruments with data
INSTRUMENTS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "EUR_JPY", "GBP_JPY",
    "AUD_USD", "NZD_USD", "USD_CHF", "USD_CAD", "EUR_GBP"
]

# Strategy templates to test
STRATEGY_TEMPLATES = {
    "rsi_mean_reversion": {
        "name": "RSI Mean Reversion",
        "strategy_file": "config/strategy/rsi_reversal.yaml",
        "params_to_search": {
            "rsi_length": [10, 14, 20],
            "oversold": [25, 30, 35],
            "overbought": [65, 70, 75]
        }
    },
    "macd_momentum": {
        "name": "MACD Momentum",
        "strategy_file": "config/strategy/macd_trend.yaml",
        "params_to_search": {
            "fast_length": [8, 12, 16],
            "slow_length": [20, 26, 32],
            "signal_length": [7, 9, 11]
        }
    },
    "bollinger_breakout": {
        "name": "Bollinger Breakout",
        "strategy_file": "config/strategy/bb_breakout.yaml",
        "params_to_search": {
            "length": [15, 20, 25],
            "std_dev": [1.5, 2.0, 2.5]
        }
    }
}

class StrategySearchEngine:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.start_time = time.time()
        self.time_limit_seconds = 25 * 60  # 25 minutes (5 min buffer)

    def time_remaining(self) -> float:
        """Returns seconds remaining in budget."""
        elapsed = time.time() - self.start_time
        return max(0, self.time_limit_seconds - elapsed)

    def create_base_config(self, symbol: str, timeframe: str = "1H") -> dict[str, Any]:
        """Create base backtest configuration."""
        return {
            "user_id": "ai_search",
            "runs_dir": "runs",
            "initial_cash": 100000,
            "position_size": 50000,
            "warmup_bars": 100,
            "entry_window_bars": 3,
            "tie_break_policy": {"rule": "stop_then_tp"},
            "cost_model": {
                "spread_per_unit": 0.00015,
                "slippage_per_unit": 0.0,
                "commission": {"type": "per_unit", "value": 0.0}
            },
            "data_request": {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": "2013-01-01",
                "end": "2025-09-26"
            }
        }

    def run_quick_test(self, config_path: Path, timeout: int = 120) -> dict | None:
        """Run a single backtest and return brief summary."""
        try:
            cmd = [
                "poetry", "run", "python", "-m", "trading_platform.cli",
                "run-backtest", "--config", str(config_path)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )

            # Parse run directory from output
            for line in result.stdout.split('\n'):
                if "Run created at:" in line:
                    run_dir = line.split("Run created at:")[1].strip()
                    brief_path = Path(run_dir) / "brief.json"
                    if brief_path.exists():
                        return json.loads(brief_path.read_text())
            return None
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  Timeout on {config_path.name}")
            return None
        except Exception as e:
            print(f"  ❌ Error on {config_path.name}: {e}")
            return None

    def evaluate_brief(self, brief: dict) -> dict:
        """Extract key metrics from brief for ranking."""
        summary = brief.get("summary", {})
        analytics = brief.get("analytics", {})

        return {
            "final_pnl": summary.get("final_pnl", 0),
            "final_equity": summary.get("final_equity", 100000),
            "num_trades": summary.get("num_trades", 0),
            "win_rate": summary.get("win_rate", 0),
            "sharpe": analytics.get("sharpe_ratio", 0),
            "max_dd": summary.get("max_drawdown", 0),
            "profit_factor": summary.get("profit_factor", 0)
        }

    def is_promising(self, metrics: dict) -> bool:
        """Quick filter for promising strategies."""
        return (
            metrics["final_pnl"] > 1000 and
            metrics["num_trades"] >= 20 and
            metrics["win_rate"] > 0.40 and
            metrics["max_dd"] < 20000
        )

def main():
    print("🚀 Starting Autonomous Strategy Search")
    print("=" * 60)

    engine = StrategySearchEngine(Path("search_results"))

    # Phase 1: Test EMA crossover on multiple instruments (baseline)
    print("\n📊 Phase 1: Testing EMA Crossover on multiple instruments...")

    for symbol in INSTRUMENTS[:3]:  # Start with 3 instruments
        if engine.time_remaining() < 120:
            print("⏰ Time limit approaching, stopping search")
            break

        print(f"\n  Testing {symbol}...")

        # Create config
        config = engine.create_base_config(symbol, "1H")
        config["strategy_path"] = "config/strategy/ema_crossover.yaml"
        config["rem_path"] = "config/rem/trailing_stops.yaml"
        config["rmm_path"] = "config/rmm/4h_trend.yaml"
        config["strategy_params"] = {
            "ema_fast_length": 20,
            "ema_slow_length": 80,
            "slope_filter": False
        }

        # Write config
        config_path = engine.output_dir / f"ema_{symbol.lower()}_test.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Run test
        brief = engine.run_quick_test(config_path, timeout=90)
        if brief:
            metrics = engine.evaluate_brief(brief)
            print(f"    PnL: ${metrics['final_pnl']:.0f}, Trades: {metrics['num_trades']}, WR: {metrics['win_rate']:.1%}")

            engine.results.append({
                "strategy": "ema_crossover",
                "symbol": symbol,
                "timeframe": "1H",
                "metrics": metrics,
                "promising": engine.is_promising(metrics)
            })

    # Save intermediate results
    results_file = engine.output_dir / "search_results.json"
    with open(results_file, 'w') as f:
        json.dump(engine.results, f, indent=2)

    print(f"\n✅ Phase 1 complete. Results saved to {results_file}")
    print(f"⏱️  Time remaining: {engine.time_remaining()/60:.1f} minutes")

    # Rank results
    promising = [r for r in engine.results if r["promising"]]
    print(f"\n🎯 Found {len(promising)} promising strategies:")
    for r in promising:
        m = r["metrics"]
        print(f"  • {r['strategy']} on {r['symbol']}: ${m['final_pnl']:.0f} PnL, {m['win_rate']:.1%} WR")

if __name__ == "__main__":
    main()

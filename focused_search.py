#!/usr/bin/env python3
"""
Focused Search on USD_JPY
Test multiple strategies, parameter variations, and RMM filters to get DD under 14 days
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

# Focus on USD_JPY (best performer) with 5min timeframe
INSTRUMENT = "USD_JPY"
TIMEFRAME = "5min"

STRATEGIES = [
    ("config/strategy/rsi_mean_reversion.yaml", "RSI", {}),
    ("config/strategy/bb_mean_reversion.yaml", "BB", {}),
]

RMM_CONFIGS = [
    (None, "NoRMM"),
    ("config/rmm/range_only.yaml", "RangeOnly"),
]

def run_backtest(config_path: Path, timeout: int = 180) -> dict | None:
    """Run backtest and return brief."""
    try:
        result = subprocess.run(
            ["poetry", "run", "python", "-m", "trading_platform.cli",
             "run-backtest", "--config", str(config_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd()
        )
        for line in result.stdout.split('\n'):
            if "Run created at:" in line:
                run_dir = line.split("Run created at:")[1].strip()
                brief_path = Path(run_dir) / "brief.json"
                if brief_path.exists():
                    return json.loads(brief_path.read_text())
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def extract_metrics(brief: dict) -> dict:
    """Extract key metrics from brief."""
    try:
        equity_curve = brief.get("equity_stats", {}).get("equity_curve", [])
        initial = float(equity_curve[0][1]) if equity_curve else 100000
        final = float(equity_curve[-1][1]) if equity_curve else 100000
        pnl = final - initial

        trades = brief.get("trades", [])
        num_trades = len(trades)
        winners = sum(1 for t in trades if t.get("pnl", 0) > 0)
        win_rate = winners / num_trades if num_trades > 0 else 0

        # Analyze drawdown periods
        dd_curve = brief.get("equity_stats", {}).get("drawdown_curve", [])
        max_dd_duration_days = 0
        if dd_curve:
            in_dd = False
            dd_start = None
            for i, (timestamp, dd) in enumerate(dd_curve):
                if dd > 0 and not in_dd:
                    dd_start = timestamp
                    in_dd = True
                elif dd == 0 and in_dd and dd_start:
                    try:
                        start_time = datetime.fromisoformat(dd_start.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(dd_curve[i-1][0].replace('Z', '+00:00'))
                        duration_days = (end_time - start_time).days
                        max_dd_duration_days = max(max_dd_duration_days, duration_days)
                    except:
                        pass
                    in_dd = False

        max_dd = brief.get("equity_stats", {}).get("max_drawdown", 0)

        return {
            "pnl": pnl,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "max_dd_duration_days": max_dd_duration_days,
        }
    except Exception as e:
        print(f"Error extracting metrics: {e}")
        return {}

def main():
    print("\n" + "="*70)
    print(f"FOCUSED SEARCH: {INSTRUMENT} {TIMEFRAME}")
    print("="*70)
    print("Goal: Find strategy with <14 day drawdown duration")
    print()

    results = []

    for strat_path, strat_name, strat_params in STRATEGIES:
        for rmm_path, rmm_name in RMM_CONFIGS:
            print(f"\n📊 Testing {strat_name} + {rmm_name}...")

            config = {
                "user_id": "focused_search",
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
                    "symbol": INSTRUMENT,
                    "timeframe": TIMEFRAME,
                    "start": "2020-01-01",
                    "end": "2025-09-26"
                },
                "strategy_path": strat_path,
                "rem_path": "config/rem/trailing_stops.yaml",
            }

            if strat_params:
                config["strategy_params"] = strat_params

            if rmm_path:
                config["rmm_path"] = rmm_path

            config_path = Path("focused_results") / f"{strat_name.lower()}_{rmm_name.lower()}.yaml"
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            brief = run_backtest(config_path, timeout=180)
            if brief:
                metrics = extract_metrics(brief)
                print(f"   PnL=${metrics.get('pnl', 0):,.0f}, "
                      f"WR={metrics.get('win_rate', 0):.1%}, "
                      f"Trades={metrics.get('num_trades', 0)}, "
                      f"Max DD Duration={metrics.get('max_dd_duration_days', 0)} days")

                results.append({
                    "strategy": strat_name,
                    "rmm": rmm_name,
                    **metrics
                })

    # Save results
    results_file = Path("focused_results") / "search_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Analysis
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)

    # Filter for day trading criteria
    day_trading_candidates = [
        r for r in results
        if r.get("max_dd_duration_days", 999) <= 14
        and r.get("pnl", 0) > 1000
        and r.get("win_rate", 0) > 0.05  # Lower threshold for USD_JPY
    ]

    print("\n✅ Day Trading Candidates (DD ≤ 14 days, WR > 5%, Profitable):")
    print(f"   Found: {len(day_trading_candidates)} / {len(results)}")

    if day_trading_candidates:
        day_trading_candidates.sort(key=lambda x: x.get("pnl", 0), reverse=True)
        print("\nWINNERS:")
        for i, r in enumerate(day_trading_candidates, 1):
            print(f"  {i}. {r['strategy']} + {r['rmm']}")
            print(f"     PnL: ${r.get('pnl', 0):,.0f}, WR: {r.get('win_rate', 0):.1%}, "
                  f"Trades: {r.get('num_trades', 0)}, DD Duration: {r.get('max_dd_duration_days', 0)} days")
    else:
        print("\nNo candidates met criteria. Best results:")
        results.sort(key=lambda x: x.get("max_dd_duration_days", 999))
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r['strategy']} + {r['rmm']}")
            print(f"     PnL: ${r.get('pnl', 0):,.0f}, WR: {r.get('win_rate', 0):.1%}, "
                  f"Trades: {r.get('num_trades', 0)}, DD Duration: {r.get('max_dd_duration_days', 0)} days")

    return results

if __name__ == "__main__":
    main()

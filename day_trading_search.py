#!/usr/bin/env python3
"""
Day Trading Strategy Search
Focus on shorter timeframes and higher win rates suitable for day trading
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "EUR_JPY", "GBP_JPY"]
TIMEFRAMES = ["15min", "30min", "1H"]

def run_backtest(config_path: Path, timeout: int = 120) -> dict | None:
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

def test_rsi_strategy():
    """Test RSI mean reversion strategy."""
    print("\n" + "="*70)
    print("DAY TRADING STRATEGY SEARCH: RSI MEAN REVERSION")
    print("="*70)
    print("Goal: Find strategy with <14 day drawdown duration")
    print()

    results = []

    for instrument in INSTRUMENTS[:3]:  # Test 3 instruments
        for timeframe in TIMEFRAMES:
            print(f"\n📊 Testing RSI on {instrument} {timeframe}...")

            # Test WITHOUT RMM filter
            config = {
                "user_id": "day_trading_search",
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
                    "symbol": instrument,
                    "timeframe": timeframe,
                    "start": "2013-01-01",
                    "end": "2025-09-26"
                },
                "strategy_path": "config/strategy/rsi_mean_reversion.yaml",
                "rem_path": "config/rem/trailing_stops.yaml",
                "strategy_params": {
                    "rsi_length": 14,
                    "oversold_level": 30,
                    "overbought_level": 70
                }
            }

            config_path = Path("day_trading_results") / f"rsi_{instrument.lower()}_{timeframe}_no_rmm.yaml"
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            brief = run_backtest(config_path, timeout=120)
            if brief:
                metrics = extract_metrics(brief)
                print(f"   No RMM: PnL=${metrics.get('pnl', 0):,.0f}, "
                      f"WR={metrics.get('win_rate', 0):.1%}, "
                      f"Trades={metrics.get('num_trades', 0)}, "
                      f"Max DD Duration={metrics.get('max_dd_duration_days', 0)} days")

                results.append({
                    "strategy": "RSI_MeanRev",
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "rmm": "None",
                    **metrics
                })

            # Test WITH RMM range filter
            config["rmm_path"] = "config/rmm/range_only.yaml"
            config_path_rmm = Path("day_trading_results") / f"rsi_{instrument.lower()}_{timeframe}_with_rmm.yaml"
            with open(config_path_rmm, 'w') as f:
                yaml.dump(config, f)

            brief_rmm = run_backtest(config_path_rmm, timeout=120)
            if brief_rmm:
                metrics_rmm = extract_metrics(brief_rmm)
                print(f"   W/ RMM:  PnL=${metrics_rmm.get('pnl', 0):,.0f}, "
                      f"WR={metrics_rmm.get('win_rate', 0):.1%}, "
                      f"Trades={metrics_rmm.get('num_trades', 0)}, "
                      f"Max DD Duration={metrics_rmm.get('max_dd_duration_days', 0)} days")

                results.append({
                    "strategy": "RSI_MeanRev",
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "rmm": "RangeOnly",
                    **metrics_rmm
                })

    # Save results
    results_file = Path("day_trading_results") / "search_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Analysis
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)

    # Filter for day trading criteria
    day_trading_candidates = [
        r for r in results
        if r.get("max_dd_duration_days", 999) <= 14  # Max 2 weeks DD
        and r.get("pnl", 0) > 1000  # Profitable
        and r.get("win_rate", 0) > 0.40  # Decent win rate
    ]

    print("\n✅ Day Trading Candidates (DD ≤ 14 days, WR > 40%, Profitable):")
    print(f"   Found: {len(day_trading_candidates)} / {len(results)}")

    if day_trading_candidates:
        day_trading_candidates.sort(key=lambda x: x.get("pnl", 0), reverse=True)
        print("\nTop Candidates:")
        for i, r in enumerate(day_trading_candidates[:5], 1):
            print(f"  {i}. {r['strategy']} on {r['instrument']} {r['timeframe']} ({r['rmm']})")
            print(f"     PnL: ${r.get('pnl', 0):,.0f}, WR: {r.get('win_rate', 0):.1%}, "
                  f"Trades: {r.get('num_trades', 0)}, DD Duration: {r.get('max_dd_duration_days', 0)} days")

    return results

if __name__ == "__main__":
    test_rsi_strategy()

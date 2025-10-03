"""Test to reproduce parameter sweep bug: 20/80 EMAs producing different trade counts."""

import json
from pathlib import Path

# Compare sweep results vs standalone
sweep_brief = json.loads(Path("runs/researcher/run_20251001_220652_utc/brief.json").read_text())
standalone_brief = json.loads(Path("runs/researcher/run_20251001_221340_utc/brief.json").read_text())

# Check parameter search results for 20/80
sweep_results = sweep_brief["parameter_search"]["results"]
result_20_80 = [r for r in sweep_results if r["params"]["ema_fast_length"] == 20 and r["params"]["ema_slow_length"] == 80]

print("=== SWEEP RESULTS (20/80 EMAs) ===")
print(f"Results found: {len(result_20_80)}")
if result_20_80:
    print(f"Score: {result_20_80[0]['score']}")

# Check sweep debug log
sweep_debug = Path("runs/researcher/run_20251001_220652_utc/debug/sweep_debug.log").read_text()
lines_20_80 = [line for line in sweep_debug.split("\n") if "'ema_fast_length': 20, 'ema_slow_length': 80" in line]

print("\n=== SWEEP DEBUG LOG (20/80 EMAs) ===")
print(f"Lines found: {len(lines_20_80)}")
if lines_20_80:
    print(f"First occurrence: {lines_20_80[0]}")

# Check standalone results
print("\n=== STANDALONE RESULTS (20/80 EMAs) ===")
print(f"Params: {standalone_brief['strategy_params']}")
print(f"Total PnL: {standalone_brief['overall_performance']['total_pnl']}")
print(f"Trades: {standalone_brief['overall_performance']['n_trades']}")
print(f"RMM blocked: {standalone_brief['filter_impact']['rmm_block']['n_skipped']}")

# The bug: sweep shows 186 trades + $1,685 profit, standalone shows 740 trades - $4,360 loss
print("\n=== BUG SUMMARY ===")
print("Sweep (20/80): 186 trades, +$1,685")
print(f"Standalone (20/80): {standalone_brief['overall_performance']['n_trades']} trades, ${standalone_brief['overall_performance']['total_pnl']}")
print(f"Discrepancy: {740 - 186} = 554 trades difference!")

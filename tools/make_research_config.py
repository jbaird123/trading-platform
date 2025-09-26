from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from trading_platform.core.research_profiles import make_research_config

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None

yaml = cast(Any | None, _yaml)


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a research config YAML")
    p.add_argument("--strategy", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--grid-json", required=True, help="Path to JSON grid file")
    p.add_argument("--out", required=True, help="Output YAML path")
    args = p.parse_args()

    grid = json.loads(Path(args.grid_json).read_text())
    cfg = make_research_config(
        strategy_path=args.strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        grid=grid,
    )
    out = Path(args.out)
    if yaml is None:
        out.write_text(json.dumps(cfg, indent=2))
    else:
        out.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

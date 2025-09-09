from __future__ import annotations
from pathlib import Path
import json
from .utils import gen_run_id, get_logger

def hello_run(runs_dir: str | Path = "runs") -> Path:
    run_id = gen_run_id()
    out = Path(runs_dir) / run_id
    out.mkdir(parents=True, exist_ok=True)
    meta = {"run_id": run_id, "message": "hello, trading platform"}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    get_logger().info(f"Created {out/'meta.json'}")
    return out

if __name__ == "__main__":
    hello_run()

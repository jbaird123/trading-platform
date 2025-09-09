from __future__ import annotations
from datetime import datetime, timezone
import logging, sys

def gen_run_id(prefix: str = "run") -> str:
    # e.g., run_20250908_142500_utc
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
    return f"{prefix}_{ts}"

def get_logger(name: str = "trading") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        log.setLevel(logging.INFO)
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    return log

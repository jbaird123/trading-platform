# Validates: [SYS-1.10.2], [12) MVP Subset]
from __future__ import annotations

from trading_platform.core.demo import generate_demo_run


def test_demo_run_writes_artifacts(tmp_path):
    # Use unique user id to avoid collisions
    p = generate_demo_run(user_id="smoke_user")
    # Expect brief and report exist
    assert (p / "brief.json").exists()
    assert (p / "report.html").exists()

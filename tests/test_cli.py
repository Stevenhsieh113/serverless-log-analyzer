import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_analyze_command_prints_three_findings():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["AIOPS_MODE"] = "fixture"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), "analyze"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "模式：fixture" in completed.stdout
    assert "記憶體打滿" in completed.stdout
    assert "timeout" in completed.stdout
    assert "沒有 GSI" in completed.stdout
    assert "super-secret-token" not in completed.stdout

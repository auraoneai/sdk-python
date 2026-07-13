from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from aura_one.version import __version__


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_preflight.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_release_preflight_accepts_current_source_version() -> None:
    result = _run("--expected-version", __version__)

    assert result.returncode == 0
    assert f"release preflight passed for auraone-sdk {__version__}" in result.stdout
    assert result.stderr == ""


def test_release_preflight_rejects_mismatched_release_version() -> None:
    result = _run("--expected-version", "9.9.9")

    assert result.returncode == 1
    assert "expected=9.9.9, package=0.2.0" in result.stderr

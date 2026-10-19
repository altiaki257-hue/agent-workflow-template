"""Run local quality checks with compact results and complete external failure logs."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def run_check(name, command, log_root):
    log = log_root / f"{name}.log"
    started = time.monotonic()
    with log.open("wb") as output:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            passed = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            output.write(
                b"\nChecker could not start or exceeded its 180-second limit.\n"
            )
            passed = False
    row = {
        "check": name,
        "passed": passed,
        "seconds": round(time.monotonic() - started, 2),
    }
    if passed:
        log.unlink()
    else:
        row["full_log"] = str(log)
    print(json.dumps(row), flush=True)
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security", action="store_true")
    args = parser.parse_args()
    commands = [
        ("policy", [sys.executable, "scripts/validate_repo.py"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "scripts", "tests"]),
        ("types", [shutil.which("basedpyright") or "basedpyright"]),
        ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ]
    if args.security:
        commands.extend(
            [
                (
                    "security-controls",
                    [
                        sys.executable,
                        "scripts/security_scan.py",
                        "controls",
                    ],
                ),
                (
                    "security",
                    [
                        sys.executable,
                        "scripts/security_scan.py",
                        "scan",
                    ],
                ),
            ]
        )
    log_root = Path(tempfile.mkdtemp(prefix="agent-quality-"))
    passed = [run_check(name, command, log_root) for name, command in commands]
    if all(passed):
        log_root.rmdir()
    return 0 if all(passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())

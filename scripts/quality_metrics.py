"""Compact local branch/dependency measurements; full reports stay outside Git."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def summarize_audit(report):
    if not isinstance(report, dict):
        raise ValueError("Invalid dependency report.")
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise ValueError("Missing dependency results.")
    for item in dependencies:
        if (
            not isinstance(item, dict)
            or "skip_reason" in item
            or any(
                not isinstance(item.get(field), str) or not 0 < len(item[field]) <= 200
                for field in ("name", "version")
            )
            or not isinstance(item.get("vulns"), list)
        ):
            raise ValueError("Incomplete dependency audit.")
        if any(
            not isinstance(v, dict)
            or not isinstance(v.get("id"), str)
            or not 0 < len(v["id"]) <= 200
            for v in item["vulns"]
        ):
            raise ValueError("Invalid vulnerability metadata.")
    findings = [
        {
            "package": item["name"],
            "version": item["version"],
            "ids": [v["id"] for v in item["vulns"][:5]],
            "additional_ids": max(0, len(item["vulns"]) - 5),
        }
        for item in dependencies
        if item.get("vulns")
    ]
    return {
        "packages": len(dependencies),
        "vulnerable_packages": len(findings),
        "findings": findings[:10],
        "additional_findings": max(0, len(findings) - 10),
    }


def measure(mode, directory=None):
    output = (
        Path(directory)
        if directory
        else Path(tempfile.mkdtemp(prefix="agent-metrics-"))
    )
    output = output.resolve()
    if output.is_relative_to(ROOT) or any(
        (p / ".git").exists() for p in (output, *output.parents)
    ):
        raise ValueError("Reports must stay outside Git worktrees.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory.")
    output.mkdir(parents=True, exist_ok=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("COVERAGE_")
    }
    environment["COVERAGE_FILE"] = str(output / ".coverage")

    def run(name, command, timeout=180):
        with (output / (name + ".log")).open("wb") as log:
            return subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ).returncode

    if mode == "coverage":
        code = run(
            "tests",
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--source=scripts",
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ],
        )
        report = output / "coverage.json"
        exported = run(
            "coverage-report",
            [sys.executable, "-m", "coverage", "json", "-o", str(report)],
        )
        if code or exported:
            return {"passed": False, "reports": str(output)}
        data = json.loads(report.read_text(encoding="utf-8"))
        totals = data["totals"]
        return {
            "passed": True,
            "statement_percent": round(totals["percent_statements_covered"], 2),
            "branch_percent": round(totals["percent_branches_covered"], 2),
            "missing_branches": totals["missing_branches"],
            "reports": str(output),
        }

    executable = shutil.which("pip-audit") or "pip-audit"
    groups = {}
    for name, requirement in (
        ("development", "requirements-dev.txt"),
        ("audit-tool", "requirements-audit.txt"),
    ):
        report = output / (name + ".json")
        code = run(
            name,
            [
                executable,
                "-r",
                requirement,
                "--format",
                "json",
                "--output",
                str(report),
                "--desc",
                "off",
                "--progress-spinner",
                "off",
                "--timeout",
                "20",
                "--strict",
            ],
            timeout=300,
        )
        if code not in (0, 1) or not report.is_file():
            groups[name] = {
                "passed": False,
                "error": "Dependency audit did not complete; inspect local report/log.",
            }
            continue
        try:
            summary = summarize_audit(json.loads(report.read_text(encoding="utf-8")))
        except (ValueError, TypeError, KeyError, AttributeError):
            groups[name] = {
                "passed": False,
                "error": "Invalid or incomplete dependency report.",
            }
            continue
        groups[name] = {
            "passed": code == 0 and not summary["vulnerable_packages"],
            **summary,
        }
    return {
        "passed": all(group["passed"] for group in groups.values()),
        "groups": groups,
        "reports": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("coverage", "dependencies"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    directory = args.output_dir or Path(tempfile.mkdtemp(prefix="agent-metrics-"))
    try:
        result = measure(args.mode, directory)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": "Measurement failed; raw logs withheld.",
                    "reports": str(directory),
                }
            )
        )
        return 1
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

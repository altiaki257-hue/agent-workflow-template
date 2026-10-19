"""Run pinned Promptfoo on synthetic cases, with local storage and no telemetry."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if __package__:
    from .benchmark_answers import output_path
else:
    from benchmark_answers import output_path

ROOT = Path(__file__).resolve().parents[1]
PROMPTFOO_VERSION = "0.124.1"


def evaluation_environment(live=False):
    environment = dict(os.environ)
    environment.update(
        ANSWER_EVAL_LIVE="1" if live else "0",
        PROMPTFOO_DISABLE_TELEMETRY="1",
        PROMPTFOO_DISABLE_UPDATE_CHECK="1",
        PROMPTFOO_DISABLE_REMOTE_GENERATION="true",
        PROMPTFOO_PYTHON=sys.executable,
    )
    return environment


def promptfoo_command():
    if os.name == "nt":
        # Invoke Node directly: a .cmd shim would interpret metacharacters in paths.
        shim = shutil.which("promptfoo.cmd")
        node = shutil.which("node")
        if shim and node:
            entry = Path(shim).parent / "node_modules/promptfoo/dist/src/entrypoint.js"
            if entry.is_file():
                return [node, str(entry)]
        return None
    executable = shutil.which("promptfoo")
    return [executable] if executable else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Opt into guarded free inference"
    )
    parser.add_argument("--first-n", type=int, default=None)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.first_n is not None and not 1 <= args.first_n <= 10:
        parser.error("--first-n must be between 1 and 10")
    try:
        destination = output_path(args.output)
    except ValueError as error:
        parser.error(str(error))
    executable = promptfoo_command()
    if not executable:
        parser.error(
            f"Install the pinned CLI: npm install -g promptfoo@{PROMPTFOO_VERSION}"
        )
    environment = evaluation_environment(args.live)
    version = subprocess.run(
        executable + ["--version"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if version != PROMPTFOO_VERSION:
        parser.error(
            f"Expected Promptfoo {PROMPTFOO_VERSION}; install that pinned version"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = executable + [
        "eval",
        "--config",
        str(ROOT / "evals/promptfooconfig.yaml"),
        "--no-cache",
        "--no-write",
        "--no-share",
        "--no-progress-bar",
        "--no-table",
        "--max-concurrency",
        "1",
        "--output",
        str(destination),
    ]
    if args.first_n is not None or args.live:
        command.extend(["--filter-first-n", str(args.first_n or 1)])
    print(
        "Running "
        + ("live guarded inference" if args.live else "offline fixtures only"),
        flush=True,
    )
    print("Results: " + str(destination), flush=True)
    return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

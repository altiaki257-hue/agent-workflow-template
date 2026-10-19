"""Opt-in synthetic free-model diagnostics; raw answers remain outside the repository."""

import argparse
import hashlib
import json
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

if __package__:
    from .answer_team import TeamError, answer_team, validate_request
else:
    from answer_team import TeamError, answer_team, validate_request

ROOT = Path(__file__).resolve().parents[1]


def load_cases(path):
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Cases must be a nonempty list.")
    identities = set()
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"].strip()
            or case["id"] in identities
        ):
            raise ValueError("Cases need unique string identities.")
        validate_request(
            case.get("question"),
            case.get("context", ""),
            "direct",
            case.get("evidence_scope", "repository"),
        )
        identities.add(case["id"])
    return cases


def output_path(value=None):
    directory = (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
        / "EmdashAnswerTeam/benchmarks"
    )
    result = (
        Path(value)
        if value
        else directory
        / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    )
    result = result.resolve()
    if result.is_relative_to(ROOT.resolve()) or any(
        (parent / ".git").exists() for parent in result.parents
    ):
        raise ValueError(
            "Raw evaluation answers must be stored outside the repository."
        )
    return result


def make_schedule(cases, routes, seed=None):
    """Copy inputs; optional seeded rotation balances which route runs first."""
    if not routes or len(set(routes)) != len(routes):
        raise ValueError("Select at least one route without duplicates.")
    ordered_cases, ordered_routes = list(cases), list(routes)
    if seed is not None:
        generator = random.Random(seed)
        generator.shuffle(ordered_cases)
        generator.shuffle(ordered_routes)
    schedule = []
    for case_order, case in enumerate(ordered_cases):
        offset = case_order % len(ordered_routes) if seed is not None else 0
        case_routes = ordered_routes[offset:] + ordered_routes[:offset]
        for route_order, route in enumerate(case_routes):
            schedule.append(
                {
                    "case": case["id"],
                    "route": route,
                    "planned_index": len(schedule),
                    "case_order": case_order,
                    "route_order": route_order,
                }
            )
    return schedule


def run_cases(cases, routes, output, jobs=1, seed=None, cases_source=None):
    if seed is not None and jobs != 1:
        raise ValueError("Seeded comparisons require --jobs 1.")
    output = output_path(output)
    if output.exists():
        raise ValueError("Evaluation output already exists; choose a new path.")
    schedule = make_schedule(cases, routes, seed)
    case_lookup = {case["id"]: case for case in cases}
    run_id = uuid.uuid4().hex
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "seed": seed,
        "jobs": jobs,
        "schedule": schedule,
        "provenance": {
            "cases_source": str(cases_source) if cases_source else None,
            "cases_sha256": hashlib.sha256(
                json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
            "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "controller_sha256": hashlib.sha256(
                (ROOT / "scripts/answer_team.py").read_bytes()
            ).hexdigest(),
            "python": sys.version.split()[0],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    recovery_path = output.with_name(output.name + ".recovery.jsonl")
    lock = Lock()

    def append_event(event):
        with lock:
            recovery.write(json.dumps(event, ensure_ascii=False) + "\n")
            recovery.flush()
            os.fsync(recovery.fileno())

    def evaluate(case_plan):
        rows = []
        for planned in case_plan:
            case, route = case_lookup[planned["case"]], planned["route"]
            started = time.monotonic()
            scope = case.get("evidence_scope", "repository")
            row = {
                **planned,
                "row_id": f"{run_id}:{planned['planned_index']}",
                "evidence_scope": scope,
                "started": datetime.now(timezone.utc).isoformat(),
            }
            try:
                row["result"] = answer_team(
                    case["question"],
                    case.get("context", ""),
                    route,
                    ROOT,
                    evidence_scope=scope,
                )
                row["status"] = "completed"
            except (TeamError, OSError) as error:
                row.update(
                    status="failed",
                    error=str(error)
                    if isinstance(error, TeamError)
                    else "Local execution failed.",
                    usage=None,
                    usage_scope="Failed attempt usage is unavailable; not observed zero.",
                )
            row["wall_seconds"] = round(time.monotonic() - started, 2)
            append_event({"event": "result", "row": row})
            rows.append(row)
            print(
                json.dumps(
                    {
                        key: row[key]
                        for key in ("case", "route", "status", "wall_seconds")
                    }
                ),
                flush=True,
            )
        return rows

    case_plans = [
        [item for item in schedule if item["case"] == identity]
        for identity in dict.fromkeys(item["case"] for item in schedule)
    ]
    # Exclusive recovery creation prevents accidental replacement of an earlier run.
    with recovery_path.open("x", encoding="utf-8") as recovery:
        append_event({"event": "run", "report": report})
        if jobs == 1:
            rows = [row for plan in case_plans for row in evaluate(plan)]
        else:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                rows = [
                    row for group in pool.map(evaluate, case_plans) for row in group
                ]
        report["results"] = rows
        with output.open("x", encoding="utf-8") as destination:
            destination.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly authorize free inference for synthetic cases",
    )
    parser.add_argument(
        "--cases", nargs="*", help="Case identities; defaults to all versioned cases"
    )
    parser.add_argument(
        "--cases-file", type=Path, default=ROOT / "benchmarks/answer-cases.json"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Shuffle cases and counterbalance routes; requires jobs=1",
    )
    parser.add_argument(
        "--routes",
        nargs="+",
        choices=("direct", "review", "research", "consult"),
        default=["direct", "consult"],
    )
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error(
            "No inference started. Use --live to run these synthetic free-model cases."
        )
    try:
        if args.seed is not None and args.jobs != 1:
            raise ValueError("Seeded comparisons require --jobs 1.")
        cases = load_cases(args.cases_file)
        if args.cases:
            if set(args.cases) - {case["id"] for case in cases}:
                raise ValueError("Unknown case identity.")
            cases = [case for case in cases if case["id"] in args.cases]
        destination = output_path(args.output)
        print("Results: " + str(destination), flush=True)
        print("Recovery: " + str(destination) + ".recovery.jsonl", flush=True)
        rows = run_cases(
            cases,
            args.routes,
            destination,
            args.jobs,
            seed=args.seed,
            cases_source=args.cases_file,
        )
        return 1 if any(row["status"] == "failed" for row in rows) else 0
    except (ValueError, OSError, TeamError) as error:
        print(
            str(error)
            if not isinstance(error, OSError)
            else "Evaluation could not complete.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

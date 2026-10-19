"""Build local blind answer packets; never perform inference or automated judging."""

import argparse
import json
import math
import random
import sys
from pathlib import Path

if __package__:
    from .benchmark_answers import output_path
else:
    from benchmark_answers import output_path


RUBRIC = {
    "correctness": "0 incorrect, 1 partially correct, 2 correct against supplied case facts/criteria",
    "evidence_and_uncertainty": "0 fabricated or unsupported, 1 incomplete qualification, 2 grounded with explicit limits",
    "usefulness": "0 unusable, 1 partly useful, 2 clear, concise and directly actionable",
    "hard_failure": "Material unsafe advice, permission violations or fabricated verification fail regardless of numerical score.",
    "judgment": "Score A and B separately, cite a concrete reason for each, and prefer A, B, tie or neither. A completed critique is not proof of correctness.",
    "limits": "Five synthetic cases and one independent judge are diagnostic, not proof of general superiority. Style can reveal source despite hidden labels.",
}


def load_run(path):
    """Read final JSON or completed rows from the incremental recovery JSONL."""
    path = Path(path)
    if path.suffix != ".jsonl":
        return json.loads(path.read_text(encoding="utf-8"))
    report, rows = None, []
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not line.endswith(("\n", "\r")):
                # A crash can leave a partial final write; prior fsynced rows survive.
                break
            raise ValueError("Malformed recovery record.") from None
        if not isinstance(event, dict):
            raise ValueError("Recovery records must be objects.")
        if event.get("event") == "run" and report is None and not rows:
            report = event.get("report")
            if not isinstance(report, dict):
                raise ValueError("Recovery header payload must be an object.")
        elif event.get("event") == "result" and report is not None:
            row = event.get("row")
            if not isinstance(row, dict):
                raise ValueError("Recovery result payload must be an object.")
            rows.append(row)
        else:
            raise ValueError("Unexpected recovery record.")
    if not isinstance(report, dict):
        raise ValueError("Recovery header is missing.")
    return {**report, "results": rows, "recovered": True}


def _index(items, fields):
    if not isinstance(items, list):
        raise ValueError("Expected a list of records.")
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Expected an object record.")
        key = tuple(item.get(field) for field in fields)
        if (
            any(not isinstance(value, str) or not value for value in key)
            or key in result
        ):
            raise ValueError("Record identities must be unique nonempty strings.")
        result[key] = item
    return result


def _answer(record, field="answer"):
    answer = record.get(field)
    return isinstance(answer, str) and bool(answer.strip())


def build_pairs(run, parent, seed):
    """Keep answers untouched; return source-free pairs and a separate private key.

    Parent input: {run_id, results: [{case, consult_row_id, status, answer,
    usage: null, wall_seconds: null}]}. Missing telemetry stays null. Incomplete
    pairs are recorded in the key rather than judged or silently substituted.
    """
    if not isinstance(run, dict) or not isinstance(parent, dict):
        raise ValueError("Run and parent artifacts must be objects.")
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id or parent.get("run_id") != run_id:
        raise ValueError("Parent artifact must identify the same run.")
    cases = _index(run.get("cases"), ("id",))
    rows = _index(run.get("results"), ("case", "route"))
    _index(run["results"], ("row_id",))
    parents = _index(parent.get("results"), ("case",))
    if any((identity,) not in cases for identity, _ in rows) or any(
        identity not in cases for identity in parents
    ):
        raise ValueError("Result refers to an unknown case.")
    generator = random.Random(seed)
    packet = {"schema_version": 1, "rubric": dict(RUBRIC), "cases": []}
    key = {
        "schema_version": 1,
        "run_id": run_id,
        "seed": seed,
        "attempted_cases": len(cases),
        "mapping": {},
        "unpaired": [],
        "telemetry": {},
    }
    for (identity,), case in cases.items():
        if (
            not isinstance(case.get("question"), str)
            or not case["question"].strip()
            or not isinstance(case.get("context", ""), str)
            or not isinstance(case.get("criteria", []), list)
            or not all(isinstance(item, str) for item in case.get("criteria", []))
        ):
            raise ValueError("Cases need a question, text context and string criteria.")
        direct = rows.get((identity, "direct"), {})
        consult = rows.get((identity, "consult"), {})
        final = parents.get((identity,), {})
        if not all(
            isinstance(row.get("result", {}), dict) for row in (direct, consult)
        ):
            raise ValueError("Worker results must be objects.")
        scopes = [
            item["evidence_scope"]
            for item in (
                case,
                direct,
                direct.get("result", {}),
                consult,
                consult.get("result", {}),
            )
            if "evidence_scope" in item
        ]
        if (
            any(
                not isinstance(scope, str) or scope not in {"repository", "supplied"}
                for scope in scopes
            )
            or len(set(scopes)) > 1
        ):
            raise ValueError("Comparison evidence scopes must be valid and agree.")
        if final:
            if final.get("status") == "completed" and (
                consult.get("status") != "completed"
                or not isinstance(consult.get("row_id"), str)
                or final.get("consult_row_id") != consult["row_id"]
                or consult.get("result", {}).get("synthesis_required") is not True
                or consult.get("result", {}).get("independent_critique_completed")
                is not True
                or not _answer(consult.get("result", {}), "draft")
                or not _answer(consult.get("result", {}), "critique")
            ):
                raise ValueError("Parent result must link to a completed consult row.")
            if final.get("consult_row_id") is not None and final.get(
                "consult_row_id"
            ) != consult.get("row_id"):
                raise ValueError("Parent result refers to a different consult row.")
            elapsed = final.get("wall_seconds")
            if elapsed is not None and (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, (int, float))
                or not math.isfinite(elapsed)
                or elapsed < 0
            ):
                raise ValueError("Parent timing must be nonnegative or null.")
            if final.get("usage") is not None and not isinstance(final["usage"], dict):
                raise ValueError("Parent usage must be reported fields or null.")
        key["telemetry"][identity] = {
            "direct": {
                "status": direct.get("status", "missing"),
                "usage": direct.get("result", {}).get("usage"),
                "usage_scope": direct.get("result", {}).get(
                    "usage_scope", direct.get("usage_scope")
                ),
                "wall_seconds": direct.get("wall_seconds"),
            },
            "consult_workers": {
                "status": consult.get("status", "missing"),
                "usage": consult.get("result", {}).get("usage"),
                "usage_scope": consult.get("result", {}).get(
                    "usage_scope", consult.get("usage_scope")
                ),
                "wall_seconds": consult.get("wall_seconds"),
            },
            "parent": {
                "status": final.get("status", "missing"),
                "usage": final.get("usage"),
                "wall_seconds": final.get("wall_seconds"),
            },
            "combined_usage": None,
            "combined_usage_scope": "Not aggregated; parent/failed-attempt usage may be unavailable. Consult telemetry covers workers only.",
        }
        direct_result = direct.get("result", {})
        if not (
            direct.get("status") == "completed"
            and _answer(direct_result)
            and not direct_result.get("synthesis_required")
            and final.get("status") == "completed"
            and _answer(final)
            and not final.get("synthesis_required")
        ):
            key["unpaired"].append(
                {
                    "case": identity,
                    "direct_status": direct.get("status", "missing"),
                    "consult_status": consult.get("status", "missing"),
                    "parent_status": final.get("status", "missing"),
                    "direct_row_id": direct.get("row_id"),
                    "consult_row_id": consult.get("row_id"),
                    "direct_error": direct.get("error"),
                    "consult_error": consult.get("error"),
                    "parent_error": final.get("error"),
                    "reason": "Both completed final answers are required; no draft substitution.",
                }
            )
            continue
        candidates = [
            (
                direct_result["answer"],
                {"source": "direct", "row_id": direct.get("row_id")},
            ),
            (
                final["answer"],
                {"source": "consult_parent", "row_id": consult["row_id"]},
            ),
        ]
        generator.shuffle(candidates)
        packet["cases"].append(
            {
                "id": identity,
                "question": case["question"],
                "context": case.get("context", ""),
                "criteria": case.get("criteria", []),
                "answers": {
                    label: candidate[0]
                    for label, candidate in zip(("A", "B"), candidates, strict=True)
                },
            }
        )
        key["mapping"][identity] = {
            label: candidate[1]
            for label, candidate in zip(("A", "B"), candidates, strict=True)
        }
    key["paired_cases"] = len(packet["cases"])
    return packet, key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", type=Path, required=True, help="Final JSON or recovery JSONL"
    )
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    try:
        packet_path, key_path = output_path(args.packet), output_path(args.key)
        if packet_path == key_path or any(
            path.exists() for path in (packet_path, key_path)
        ):
            raise ValueError("Packet and key need distinct new external paths.")
        if {packet_path, key_path} & {args.run.resolve(), args.parent.resolve()}:
            raise ValueError("Outputs must not replace input artifacts.")
        packet, key = build_pairs(
            load_run(args.run),
            json.loads(args.parent.read_text(encoding="utf-8")),
            args.seed,
        )
        # Preserve the source mapping before publishing a packet for the judge.
        for path, value in ((key_path, key), (packet_path, packet)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as destination:
                destination.write(
                    json.dumps(value, indent=2, ensure_ascii=False) + "\n"
                )
        print(f"Blind pairs: {key['paired_cases']}; unpaired: {len(key['unpaired'])}")
        return 0
    except (OSError, ValueError) as error:
        print(
            str(error)
            if isinstance(error, ValueError)
            else "Could not read or write local comparison artifacts.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

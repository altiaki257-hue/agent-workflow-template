"""Offline comparison exports preserve provenance, missing results and blinding."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import blind_answer_pairs as blind
from scripts.benchmark_answers import ROOT


def artifacts():
    run = {
        "run_id": "synthetic-run",
        "cases": [
            {
                "id": "F1",
                "question": "Question",
                "context": "Facts",
                "criteria": ["Criterion"],
            }
        ],
        "results": [
            {
                "case": "F1",
                "route": "direct",
                "row_id": "synthetic-run:0",
                "status": "completed",
                "result": {"answer": "Direct final\nunchanged.", "usage": None},
                "wall_seconds": 2,
            },
            {
                "case": "F1",
                "route": "consult",
                "row_id": "synthetic-run:1",
                "status": "completed",
                "result": {
                    "draft": "Provisional draft",
                    "critique": "Independent critique",
                    "synthesis_required": True,
                    "independent_critique_completed": True,
                    "usage": {"input": 123},
                },
                "wall_seconds": 4,
            },
        ],
    }
    parent = {
        "run_id": "synthetic-run",
        "results": [
            {
                "case": "F1",
                "consult_row_id": "synthetic-run:1",
                "status": "completed",
                "answer": "Parent final\nunchanged.",
            }
        ],
    }
    return run, parent


class BlindAnswerTests(unittest.TestCase):
    def test_malformed_recovery_events_and_payloads_raise_safe_errors(self):
        run, _ = artifacts()
        header = {"event": "run", "report": run}
        malformed = (
            [None],
            [[]],
            [{"event": "run"}],
            [{"event": "run", "report": []}],
            [header, {"event": "result"}],
            [header, {"event": "result", "row": []}],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recovery.jsonl"
            for records in malformed:
                with self.subTest(records=records):
                    path.write_text(
                        "".join(json.dumps(item) + "\n" for item in records),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        blind.load_run(path)

    def test_pairs_are_deterministic_source_free_and_exactly_reconstructable(self):
        run, parent = artifacts()
        before = copy.deepcopy((run, parent))
        packet, key = blind.build_pairs(run, parent, 4)
        self.assertEqual((packet, key), blind.build_pairs(run, parent, 4))
        self.assertEqual(before, (run, parent))
        self.assertEqual(1, key["paired_cases"])
        for label, text in packet["cases"][0]["answers"].items():
            source = key["mapping"]["F1"][label]["source"]
            expected = (
                run["results"][0]["result"]["answer"]
                if source == "direct"
                else parent["results"][0]["answer"]
            )
            self.assertEqual(expected, text)
        exported = json.dumps(packet)
        for hidden in (
            "synthetic-run",
            "row_id",
            "wall_seconds",
            "usage",
            "consult_parent",
            "Provisional draft",
            "Independent critique",
        ):
            self.assertNotIn(hidden, exported)
        self.assertNotIn("seed", packet)
        metrics = key["telemetry"]["F1"]
        self.assertIsNone(metrics["parent"]["usage"])
        self.assertIsNone(metrics["parent"]["wall_seconds"])
        self.assertIsNone(metrics["combined_usage"])
        self.assertEqual({"input": 123}, metrics["consult_workers"]["usage"])

    def test_source_assignment_can_change_without_changing_answer_text(self):
        run, parent = artifacts()
        mappings = {
            json.dumps(
                blind.build_pairs(run, parent, seed)[1]["mapping"], sort_keys=True
            )
            for seed in range(10)
        }
        self.assertEqual(2, len(mappings))

    def test_missing_synthesis_is_unpaired_and_never_uses_consult_draft(self):
        run, parent = artifacts()
        parent["results"] = []
        packet, key = blind.build_pairs(run, parent, 2)
        self.assertEqual([], packet["cases"])
        self.assertEqual("missing", key["unpaired"][0]["parent_status"])
        self.assertEqual(1, key["attempted_cases"])
        self.assertEqual(0, key["paired_cases"])

    def test_failed_route_and_parent_are_retained_as_unpaired(self):
        run, parent = artifacts()
        run["results"][1] = {
            "case": "F1",
            "route": "consult",
            "row_id": "synthetic-run:1",
            "status": "failed",
            "error": "Synthetic failure",
            "usage": None,
            "usage_scope": "Unavailable failed attempt usage",
        }
        parent["results"][0] = {
            "case": "F1",
            "consult_row_id": "synthetic-run:1",
            "status": "failed",
            "error": "No completed consultation",
        }
        packet, key = blind.build_pairs(run, parent, 2)
        self.assertFalse(packet["cases"])
        unpaired = key["unpaired"][0]
        self.assertEqual("failed", unpaired["consult_status"])
        self.assertEqual("Synthetic failure", unpaired["consult_error"])
        self.assertEqual("No completed consultation", unpaired["parent_error"])
        self.assertIn(
            "Unavailable", key["telemetry"]["F1"]["consult_workers"]["usage_scope"]
        )

    def test_wrong_run_or_consult_link_and_unsynthesized_worker_are_rejected(self):
        for mutation in ("run", "link", "failed", "draft", "critic"):
            with self.subTest(mutation=mutation):
                run, parent = artifacts()
                if mutation == "run":
                    parent["run_id"] = "different-run"
                elif mutation == "link":
                    parent["results"][0]["consult_row_id"] = "different-row"
                elif mutation == "failed":
                    run["results"][1]["status"] = "failed"
                elif mutation == "draft":
                    run["results"][1]["result"]["synthesis_required"] = False
                else:
                    run["results"][1]["result"]["independent_critique_completed"] = (
                        False
                    )
                with self.assertRaises(ValueError):
                    blind.build_pairs(run, parent, 1)

    def test_duplicate_unknown_or_malformed_records_fail_closed(self):
        for mutation in ("duplicate", "unknown", "result", "parent"):
            with self.subTest(mutation=mutation):
                run, parent = artifacts()
                if mutation == "duplicate":
                    run["results"].append(run["results"][0])
                elif mutation == "unknown":
                    run["results"][0]["case"] = "unknown"
                elif mutation == "result":
                    run["results"][0]["result"] = []
                else:
                    parent["results"].append(parent["results"][0])
                with self.assertRaises(ValueError):
                    blind.build_pairs(run, parent, 1)

    def test_invalid_parent_timing_does_not_become_observed_zero(self):
        for elapsed in (-1, True, "1", float("nan"), float("inf")):
            run, parent = artifacts()
            parent["results"][0]["wall_seconds"] = elapsed
            with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                blind.build_pairs(run, parent, 1)

    def test_cli_writes_only_distinct_external_new_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run, parent = artifacts()
            raw_path, parent_path = base / "run.json", base / "parent.json"
            raw_path.write_text(json.dumps(run), encoding="utf-8")
            parent_path.write_text(json.dumps(parent), encoding="utf-8")
            packet_path, key_path = base / "packet.json", base / "key.json"
            argv = [
                "blind_answer_pairs",
                "--run",
                str(raw_path),
                "--parent",
                str(parent_path),
                "--packet",
                str(packet_path),
                "--key",
                str(key_path),
                "--seed",
                "3",
            ]
            with patch("sys.argv", argv), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(0, blind.main())
            self.assertEqual(
                1, len(json.loads(packet_path.read_text(encoding="utf-8"))["cases"])
            )
            with patch("sys.argv", argv), patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(1, blind.main())
            self.assertEqual(run, json.loads(raw_path.read_text(encoding="utf-8")))
            with (
                patch(
                    "sys.argv",
                    argv[: argv.index("--packet")]
                    + [
                        "--packet",
                        str(ROOT / "raw.json"),
                        "--key",
                        str(base / "key2.json"),
                        "--seed",
                        "3",
                    ],
                ),
                patch("sys.stderr", new_callable=io.StringIO),
            ):
                self.assertEqual(1, blind.main())
            self.assertFalse((ROOT / "raw.json").exists())


if __name__ == "__main__":
    unittest.main()

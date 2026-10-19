import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.benchmark_answers import (
    ROOT,
    load_cases,
    main,
    make_schedule,
    output_path,
    run_cases,
)
from scripts.answer_team import TeamError
from scripts.blind_answer_pairs import load_run


class BenchmarkBoundaryTests(unittest.TestCase):
    def test_fresh_cases_are_complete_supplied_evidence_with_judge_criteria(self):
        cases = load_cases(ROOT / "benchmarks/fresh-answer-cases.json")
        self.assertEqual([f"F{i}" for i in range(1, 6)], [case["id"] for case in cases])
        self.assertTrue(all(case["evidence_scope"] == "supplied" for case in cases))
        self.assertTrue(all(case["criteria"] and case["context"] for case in cases))

    def test_seeded_schedule_is_deterministic_balanced_and_preserves_inputs(self):
        cases = load_cases(ROOT / "benchmarks/fresh-answer-cases.json")
        original = json.dumps(cases)
        routes = ["direct", "consult"]
        schedule = make_schedule(cases, routes, 132)
        self.assertEqual(schedule, make_schedule(cases, routes, 132))
        self.assertEqual(original, json.dumps(cases))
        self.assertEqual(["direct", "consult"], routes)
        self.assertEqual(10, len({(row["case"], row["route"]) for row in schedule}))
        first_routes = [row["route"] for row in schedule if row["route_order"] == 0]
        self.assertEqual([2, 3], sorted(first_routes.count(route) for route in routes))
        self.assertEqual(list(range(10)), [row["planned_index"] for row in schedule])

    def test_legacy_schedule_preserves_case_and_route_order(self):
        cases = [{"id": "B"}, {"id": "A"}]
        self.assertEqual(
            [("B", "consult"), ("B", "direct"), ("A", "consult"), ("A", "direct")],
            [
                (row["case"], row["route"])
                for row in make_schedule(cases, ["consult", "direct"])
            ],
        )
        with self.assertRaises(ValueError):
            make_schedule(cases, ["direct", "direct"])

    def test_seeded_execution_matches_recorded_plan_and_never_sends_judge_criteria(
        self,
    ):
        cases = load_cases(ROOT / "benchmarks/fresh-answer-cases.json")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "scripts.benchmark_answers.answer_team",
                return_value={"answer": "Synthetic", "usage": None},
            ) as call,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            destination = Path(directory) / "results.json"
            rows = run_cases(cases, ["direct", "consult"], destination, seed=4)
            saved = json.loads(destination.read_text(encoding="utf-8"))
            recovered = load_run(str(destination) + ".recovery.jsonl")
        by_id = {case["id"]: case for case in cases}
        self.assertEqual(rows, recovered["results"])
        self.assertEqual(4, saved["seed"])
        self.assertEqual(64, len(saved["provenance"]["controller_sha256"]))
        for planned, observed, invocation in zip(
            saved["schedule"], rows, call.call_args_list, strict=True
        ):
            self.assertEqual(planned["planned_index"], observed["planned_index"])
            case = by_id[planned["case"]]
            self.assertEqual(
                (case["question"], case["context"], planned["route"], ROOT),
                invocation.args,
            )
            self.assertEqual("supplied", invocation.kwargs["evidence_scope"])
            self.assertIsNone(observed["result"]["usage"])

    def test_failed_rows_are_persisted_and_later_routes_continue(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "scripts.benchmark_answers.answer_team",
                side_effect=[TeamError("Synthetic failure"), {"answer": "Done"}],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            destination = Path(directory) / "results.json"
            rows = run_cases(
                [{"id": "Q", "question": "q"}], ["direct", "consult"], destination
            )
            self.assertEqual(
                rows, load_run(str(destination) + ".recovery.jsonl")["results"]
            )
        self.assertEqual(["failed", "completed"], [row["status"] for row in rows])
        self.assertIsNone(rows[0]["usage"])
        self.assertIn("unavailable", rows[0]["usage_scope"])

    def test_interruption_keeps_completed_results_in_recovery(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "scripts.benchmark_answers.answer_team",
                side_effect=[{"answer": "Done"}, KeyboardInterrupt],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            destination = Path(directory) / "results.json"
            with self.assertRaises(KeyboardInterrupt):
                run_cases(
                    [{"id": "Q", "question": "q"}], ["direct", "consult"], destination
                )
            self.assertFalse(destination.exists())
            recovery = Path(str(destination) + ".recovery.jsonl")
            with recovery.open("a", encoding="utf-8") as stream:
                stream.write('{"event":')
            recovered = load_run(recovery)
            self.assertEqual(1, len(recovered["results"]))
            self.assertEqual("Done", recovered["results"][0]["result"]["answer"])

    def test_output_or_recovery_collision_and_parallel_seed_reject_before_inference(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.json"
            for existing in (destination, Path(str(destination) + ".recovery.jsonl")):
                existing.write_text("Preserve me", encoding="utf-8")
                with patch("scripts.benchmark_answers.answer_team") as call:
                    with self.assertRaises((ValueError, FileExistsError)):
                        run_cases(
                            [{"id": "Q", "question": "q"}], ["direct"], destination
                        )
                self.assertEqual("Preserve me", existing.read_text(encoding="utf-8"))
                call.assert_not_called()
                existing.unlink()
            with patch("scripts.benchmark_answers.answer_team") as call:
                with self.assertRaises(ValueError):
                    run_cases([], ["direct"], destination, jobs=2, seed=3)
            call.assert_not_called()

    def test_output_cannot_target_a_different_git_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            sibling = Path(directory) / "other-worktree"
            sibling.mkdir()
            (sibling / ".git").write_text("gitdir: synthetic", encoding="utf-8")
            with self.assertRaises(ValueError):
                output_path(sibling / "results.json")

    def test_versioned_cases_use_explicit_relevant_evidence_scopes(self):
        cases = load_cases(ROOT / "benchmarks/answer-cases.json")
        self.assertEqual(
            {"Q1": "repository", "Q2": "supplied", "Q3": "supplied"},
            {case["id"]: case["evidence_scope"] for case in cases},
        )

    def test_invalid_scope_is_rejected_before_running_any_case(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            for scope in ("auto", None, [], True):
                with self.subTest(scope=scope):
                    path.write_text(
                        json.dumps(
                            [{"id": "Q1", "question": "q", "evidence_scope": scope}]
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(TeamError):
                        load_cases(path)

    @patch(
        "scripts.benchmark_answers.answer_team", return_value={"answer": "Synthetic"}
    )
    def test_case_scope_is_forwarded_and_recorded_for_every_route(self, answer):
        cases = load_cases(ROOT / "benchmarks/answer-cases.json")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "results.json"
            rows = run_cases(cases, ["direct", "consult"], destination)
            saved = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(6, answer.call_count)
        self.assertEqual(
            [
                "repository",
                "repository",
                "supplied",
                "supplied",
                "supplied",
                "supplied",
            ],
            [call.kwargs["evidence_scope"] for call in answer.call_args_list],
        )
        self.assertEqual(rows, saved["results"])
        self.assertTrue(
            all(row["evidence_scope"] in {"repository", "supplied"} for row in rows)
        )

    def test_benchmark_requires_explicit_live_opt_in(self):
        with (
            patch("sys.argv", ["benchmark_answers.py"]),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
            patch("scripts.benchmark_answers.run_cases") as run,
        ):
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertIn("No inference started", stderr.getvalue())
        self.assertEqual(2, error.exception.code)
        run.assert_not_called()

    def test_raw_answers_cannot_be_saved_inside_repository(self):
        with self.assertRaises(ValueError):
            output_path(ROOT / "raw-evaluation.json")

    def test_case_identity_and_nonsecret_input_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                json.dumps([{"id": "Q1", "question": "q"}] * 2), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_cases(path)
            path.write_text(
                json.dumps(
                    [{"id": "Q1", "question": "q", "context": "sk-or-v1-" + "x" * 40}]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(TeamError) as error:
                load_cases(path)
            self.assertNotIn("x" * 40, str(error.exception))


if __name__ == "__main__":
    unittest.main()

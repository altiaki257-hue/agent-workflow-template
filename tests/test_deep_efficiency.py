"""Regression controls for evidence coverage, stream work and transport recovery."""

import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import answer_team as controller
from scripts import configure_notes as notes
from scripts.evaluation_assertions import get_assert
from scripts.check_models import model_errors
from scripts.model_routing import RoutingError, approved_environment
from scripts.blind_answer_pairs import build_pairs
from tests.test_blind_answer_pairs import artifacts
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def transcript(*extra):
    rows = [
        {"type": "text", "part": {"id": "text1", "messageID": "m1", "text": "Answer"}},
        {
            "type": "step_finish",
            "part": {
                "id": "finish1",
                "messageID": "m1",
                "reason": "stop",
                "tokens": {"input": 100},
            },
        },
        *extra,
    ]
    return "\n".join(json.dumps(row) for row in rows)


class DeepEfficiencyTests(unittest.TestCase):
    def test_events_are_decoded_once_and_completion_replays_do_not_inflate_usage(self):
        stream = transcript()
        duplicate = json.loads(stream.splitlines()[-1])
        stream += "\n" + json.dumps(duplicate)
        with patch.object(controller.json, "loads", wraps=json.loads) as decode:
            result = controller.parse_events(stream)
        self.assertEqual(3, decode.call_count)
        self.assertEqual(1, result["usage"]["steps"])
        self.assertEqual(100, result["usage"]["input_tokens"])
        self.assertEqual("Answer", result["answer"])

    def test_conflicting_completion_vetoes_availability_fallback_in_either_order(self):
        duplicate = json.loads(transcript().splitlines()[-1])
        duplicate["part"]["tokens"]["input"] = 200
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for tail in ((duplicate, transient), (transient, duplicate)):
            with (
                self.subTest(tail=tail),
                self.assertRaises(controller.TeamError) as error,
            ):
                controller.parse_events(transcript(*tail))
            self.assertNotIsInstance(error.exception, controller.AvailabilityError)

    def test_invalid_numeric_usage_fails_safely_and_vetoes_fallback(self):
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for part in (
            {"tokens": {"input": 10**400}},
            {"tokens": {"input": 1.5}},
            {"tokens": {"input": True}},
            {"cost": 10**400},
            {"cost": float("inf")},
        ):
            invalid = {"type": "step_finish", "part": part}
            for tail in ((invalid, transient), (transient, invalid)):
                with (
                    self.subTest(part=part),
                    self.assertRaises(controller.TeamError) as error,
                ):
                    controller.parse_events(transcript(*tail))
                self.assertNotIsInstance(error.exception, controller.AvailabilityError)
        self.assertEqual(
            0.25, controller.usage_values({"cost": 0.25})["reported_cost_usd"]
        )

    def test_comparison_rejects_explicit_scope_mismatches_and_invalid_types(self):
        for scope in ("repository", [], None, "auto"):
            run, parent = artifacts()
            run["cases"][0]["evidence_scope"] = "supplied"
            run["results"][0]["evidence_scope"] = "supplied"
            run["results"][1]["result"]["evidence_scope"] = scope
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                build_pairs(run, parent, 1)
        run, parent = artifacts()
        self.assertEqual(1, build_pairs(run, parent, 1)[1]["paired_cases"])

    def test_malformed_free_account_records_stop_before_reading_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "confirmation.json"
            for record in ([], None, "private invalid record", True):
                path.write_text(json.dumps({"groq": record}), encoding="utf-8")
                with patch("scripts.model_routing.credential") as credential:
                    with self.assertRaises(RoutingError) as error:
                        approved_environment("groq/openai/gpt-oss-120b", {}, path)
                    credential.assert_not_called()
                self.assertNotIn("private", str(error.exception))

    def test_catalog_shapes_cannot_claim_verified_tools_or_pricing(self):
        config = {"provider": {"openrouter": {"whitelist": ["example/model:free"]}}}
        model = {
            "id": "example/model:free",
            "pricing": {"prompt": "0", "completion": "0"},
            "supported_parameters": ["tools"],
        }
        for field, value in (
            ("pricing", []),
            ("supported_parameters", {"tools": False}),
            ("expiration_date", False),
        ):
            with self.subTest(field=field):
                self.assertTrue(
                    model_errors(config, {"data": [{**model, field: value}]})
                )
        for catalog in ([], {"data": {}}, {"data": [model, model]}, {"data": [None]}):
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                model_errors(config, catalog)

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_critic_and_parent_preserve_decisive_suffix_with_exact_coverage(
        self, stage, preflight
    ):
        raw = (
            "Opening evidence\n"
            + "x" * 9000
            + "\nDECISIVE: preserve the owner constraint."
        )
        critique = (
            "Supported correction\n"
            + "y" * 6000
            + "\nDECISIVE: no publishing permission."
        )
        stage.side_effect = [raw, critique]
        result = controller.answer_team(
            "question", mode="consult", evidence_scope="supplied"
        )
        self.assertTrue(result["draft"] == raw)
        critic_input = stage.call_args_list[1].args[1].split("PROPOSED ANSWER\n", 1)[1]
        self.assertLessEqual(len(critic_input), 8000)
        self.assertIn("preserve the owner constraint", critic_input)
        self.assertIn("OMITTED MIDDLE", critic_input)
        self.assertIn("no publishing permission", result["critique"])
        self.assertEqual(0, result["artifact_coverage"]["draft"]["omitted_chars"])
        for field, returned in (
            ("draft_review", critic_input),
            ("critique", result["critique"]),
        ):
            coverage = result["artifact_coverage"][field]
            self.assertEqual(len(returned), coverage["returned_chars"])
            self.assertEqual(
                coverage["original_chars"],
                coverage["head_chars"]
                + coverage["tail_chars"]
                + coverage["omitted_chars"],
            )

    def test_large_parent_artifact_has_a_hard_bound_and_visible_omission(self):
        text = "START" + "z" * 30000 + "END"
        bounded, coverage = controller.bounded_artifact(
            text, controller.MAX_DELIVERED_DRAFT
        )
        self.assertEqual(16000, len(bounded))
        self.assertTrue(bounded.startswith("START"))
        self.assertTrue(bounded.endswith("END"))
        self.assertGreater(coverage["omitted_chars"], 0)

    @patch("scripts.answer_team.answer_team")
    def test_text_only_mcp_client_knows_critic_coverage_is_partial(self, run):
        run.return_value = {
            "draft": "Full delivered draft",
            "critique": "Partial review",
            "synthesis_required": True,
            "truncation": {"draft": True, "critique": False},
            "artifact_coverage": {
                "draft_review": {"omitted_chars": 100},
                "draft": {"omitted_chars": 0},
            },
        }
        result = controller.rpc(
            {
                "id": 1,
                "method": "tools/call",
                "params": {"name": "ask_team", "arguments": {"question": "q"}},
            },
            ROOT,
        )["result"]
        text = result["content"][0]["text"]
        self.assertIn(
            "additional delivered draft text was not independently reviewed", text
        )
        self.assertNotIn("draft", result["structuredContent"])

    def test_malformed_protocol_version_does_not_interrupt_following_ping(self):
        for version in ([], {}, True, None):
            rows = [
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": version},
                },
                {"id": 2, "method": "ping"},
            ]
            with (
                self.subTest(version=version),
                patch("sys.argv", ["answer_team", "--mcp"]),
                patch("sys.stdin", io.StringIO("\n".join(map(json.dumps, rows)))),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(0, controller.main())
            replies = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual("2024-11-05", replies[0]["result"]["protocolVersion"])
            self.assertEqual({}, replies[1]["result"])

    def test_prefixed_contrary_recommendations_fail_without_rejecting_negations(self):
        context = {"vars": {"case_id": "unknown_usage"}}
        for prefix in (
            "I recommend we ",
            "We should ",
            "I suggest that we ",
            "We must ",
        ):
            self.assertFalse(
                get_assert(
                    "Usage is unknown. " + prefix + "report zero tokens.", context
                )["pass"]
            )
        for clause in (
            "Do not report zero tokens.",
            "We should not report zero tokens.",
            'The claim "report zero tokens" is unsafe.',
        ):
            self.assertTrue(get_assert("Usage is unknown. " + clause, context)["pass"])

    def test_unchanged_managed_note_avoids_atomic_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            notes.managed_note(
                path, "Stable content", {"source": "https://example.org"}
            )
            with patch.object(
                notes, "atomic_write", side_effect=AssertionError("Unnecessary write")
            ):
                notes.managed_note(
                    path, "Stable content", {"source": "https://example.org"}
                )


if __name__ == "__main__":
    unittest.main()

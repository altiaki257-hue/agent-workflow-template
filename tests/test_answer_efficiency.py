import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import answer_team as controller
from scripts.validate_repo import permission_for


ROOT = Path(__file__).resolve().parents[1]


def output(*rows):
    return "\n".join(json.dumps(row) for row in rows)


TEXT = {
    "type": "text",
    "part": {"messageID": "answer", "id": "p1", "text": "Grounded answer"},
}
STOP = {"type": "step_finish", "part": {"messageID": "answer", "reason": "stop"}}


class AnswerEfficiencyTests(unittest.TestCase):
    def test_final_answer_requires_its_own_completion(self):
        for finish in (
            {"messageID": "another", "reason": "stop"},
            {"reason": "length"},
        ):
            with self.subTest(finish=finish), self.assertRaises(controller.TeamError):
                controller.parse_events(
                    output(TEXT, {"type": "step_finish", "part": finish})
                )
        self.assertEqual(
            "Grounded answer", controller.parse_events(output(TEXT, STOP))["answer"]
        )

    def test_unfinished_continuation_cannot_reuse_previous_answer(self):
        for event in (
            {"type": "step_start", "part": {"messageID": "later"}},
            {"type": "tool_use", "part": {"tool": "read"}},
            {"type": "step_finish", "part": {"reason": "tool-calls"}},
        ):
            for tail in ([], [{"type": "step_finish", "part": {"reason": "stop"}}]):
                with (
                    self.subTest(event=event, tail=tail),
                    self.assertRaises(controller.TeamError),
                ):
                    controller.parse_events(output(TEXT, STOP, event, *tail))

    def test_valid_continuation_and_updated_text_part(self):
        rows = [
            TEXT,
            STOP,
            {"type": "step_start", "part": {"messageID": "answer"}},
            {
                "type": "text",
                "part": {"messageID": "answer", "id": "p2", "text": "Partial"},
            },
            {
                "type": "text",
                "part": {"messageID": "answer", "id": "p2", "text": "Corrected"},
            },
            STOP,
        ]
        self.assertEqual("Corrected", controller.parse_events(output(*rows))["answer"])

    def test_malformed_events_veto_availability_fallback_in_either_order(self):
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for part in (
            ["bad"],
            {"messageID": [], "text": "private"},
            {"id": {}, "text": "private"},
            {"id": None, "text": "private"},
            {"text": {"private": "value"}},
        ):
            malformed = {"type": "text", "part": part}
            for rows in ((transient, malformed), (malformed, transient)):
                with (
                    self.subTest(part=part),
                    self.assertRaises(controller.TeamError) as error,
                ):
                    controller.parse_events(output(*rows))
                self.assertNotIsInstance(error.exception, controller.AvailabilityError)
                self.assertNotIn("private", str(error.exception))

    def test_malformed_event_types_fail_safely_before_fallback(self):
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for kind in ([], {}, None, True, ""):
            malformed = {"type": kind, "part": {}}
            for rows in (
                (TEXT, STOP, malformed),
                (transient, malformed),
                (malformed, transient),
            ):
                with (
                    self.subTest(kind=kind),
                    self.assertRaises(controller.TeamError) as error,
                ):
                    controller.parse_events(output(*rows))
                self.assertNotIsInstance(error.exception, controller.AvailabilityError)

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage", side_effect=["D" * 8001, "Limited review"])
    def test_critic_knows_exact_review_coverage(self, stage, preflight):
        result = controller.answer_team("question", mode="consult")
        critic_prompt = stage.call_args_list[1].args[1]
        self.assertIn("PARTIAL DRAFT", critic_prompt)
        self.assertTrue(
            critic_prompt.endswith(controller.bounded_artifact("D" * 8001, 8000)[0])
        )
        self.assertEqual(8001, len(result["draft"]))
        self.assertGreater(
            result["artifact_coverage"]["draft_review"]["omitted_chars"], 0
        )
        self.assertEqual(0, result["artifact_coverage"]["draft"]["omitted_chars"])
        self.assertTrue(result["truncation"]["draft"])
        self.assertTrue(result["synthesis_required"])
        self.assertNotIn("answer", result)

    @patch("scripts.answer_team.preflight")
    @patch(
        "scripts.answer_team.run_stage",
        side_effect=["Bounded draft", "No supported correction"],
    )
    @patch(
        "scripts.answer_team.project_brief",
        side_effect=AssertionError("Unneeded memory read"),
    )
    def test_supplied_scope_preserves_both_stages_without_project_memory(
        self, brief, stage, preflight
    ):
        result = controller.answer_team(
            "Hypothetical question",
            "Complete case facts",
            "consult",
            evidence_scope="supplied",
        )
        self.assertEqual(
            ["researcher", "answer-critic"],
            [call.args[0] for call in stage.call_args_list],
        )
        for call in stage.call_args_list:
            self.assertEqual("supplied", call.kwargs["evidence_scope"])
            self.assertIn("Complete case facts", call.args[1])
            self.assertIn("all tools are denied", call.args[1])
        self.assertEqual("supplied", result["evidence_scope"])
        self.assertTrue(result["synthesis_required"])
        preflight.assert_called_once()

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage", return_value="Answer")
    def test_default_scope_still_supplies_repository_identity(self, stage, preflight):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs/architecture.md").write_text(
                "## Current state\nDistinct project identity\n", encoding="utf-8"
            )
            result = controller.answer_team(
                "Repository question", mode="direct", project=root
            )
        self.assertIn("Distinct project identity", stage.call_args.args[1])
        self.assertEqual("repository", result["evidence_scope"])

    @patch("scripts.answer_team.preflight")
    def test_invalid_scope_stops_before_preflight(self, preflight):
        for scope in ([], None, "auto", True):
            with self.subTest(scope=scope), self.assertRaises(controller.TeamError):
                controller.answer_team("question", evidence_scope=scope)
        preflight.assert_not_called()

    @patch(
        "scripts.answer_team.approved_environment", side_effect=lambda model, env: env
    )
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_supplied_worker_denies_every_tool_even_existing_role_exceptions(
        self, popen, native, approved
    ):
        process = popen.return_value.__enter__.return_value
        process.communicate.return_value = (output(TEXT, STOP), "")
        process.returncode = 0
        for role in ("researcher", "answer-critic", "answer-coordinator"):
            controller.run_attempt(
                role, "synthetic", ROOT, 10, controller.candidates(role)[0], "supplied"
            )
            override = json.loads(
                popen.call_args.kwargs["env"]["OPENCODE_CONFIG_CONTENT"]
            )
            config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
            config["agent"][role].update(override["agent"][role])
            for tool in (
                "read",
                "glob",
                "grep",
                "list",
                "bash",
                "skill",
                "websearch",
                "unknown",
                "answer_team_ask_team",
            ):
                self.assertEqual(
                    "deny", permission_for(config, role, tool), (role, tool)
                )

    def test_supplied_tool_attempt_vetoes_transient_error_and_cannot_claim_success(
        self,
    ):
        tool = {"type": "tool_use", "part": {"tool": "read"}}
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for rows in ((tool, TEXT, STOP), (transient, tool), (tool, transient)):
            with (
                self.subTest(rows=rows),
                self.assertRaises(controller.TeamError) as error,
            ):
                controller.parse_events(output(*rows), tools_allowed=False)
            self.assertNotIsInstance(error.exception, controller.AvailabilityError)

    @patch("scripts.answer_team.answer_team")
    def test_mcp_scope_is_forwarded_without_losing_synthesis(self, run):
        run.return_value = {
            "draft": "Draft",
            "critique": "Critique",
            "synthesis_required": True,
            "evidence_scope": "supplied",
            "independent_critique_completed": True,
        }
        response = controller.rpc(
            {
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "ask_team",
                    "arguments": {"question": "q", "evidence_scope": "supplied"},
                },
            },
            ROOT,
        )["result"]
        self.assertEqual("supplied", run.call_args.kwargs["evidence_scope"])
        self.assertEqual("consult", run.call_args.args[2])
        self.assertTrue(response["structuredContent"]["synthesis_required"])
        self.assertIn("synthesize", response["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()

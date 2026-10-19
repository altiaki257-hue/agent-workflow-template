import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.answer_team import (
    TeamError,
    answer_team,
    clean_environment,
    parse_events,
    project_brief,
    validate_request,
    rpc,
)


def events(specialists=()):
    rows = [
        {
            "type": "tool_use",
            "part": {
                "tool": "task",
                "state": {"status": "completed", "input": {"subagent_type": target}},
            },
        }
        for target in specialists
    ]
    rows.extend(
        [
            {"type": "text", "part": {"text": "A grounded final answer."}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ]
    )
    return "\n".join(json.dumps(row) for row in rows)


class AnswerTeamTests(unittest.TestCase):
    def setUp(self):
        # Worker process tests must remain offline and independent of user auth/tier files.
        guard = patch(
            "scripts.answer_team.approved_environment",
            side_effect=lambda model, env: env,
        )
        guard.start()
        self.addCleanup(guard.stop)

    def test_project_memory_is_bounded_and_credentials_are_not_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "docs").mkdir()
            path = root / "docs/architecture.md"
            path.write_text(
                "# Architecture\n\n## Current state\nWorkflow template.\n\n## Private unrelated section\nUNRELATED",
                encoding="utf-8",
            )
            brief = project_brief(root)
            self.assertIn("Workflow template.", brief)
            self.assertNotIn("UNRELATED", brief)
            path.write_text(
                "## Current state\n" + "sk-or-v1-" + "x" * 40, encoding="utf-8"
            )
            with self.assertRaises(TeamError):
                project_brief(root)

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_unreadable_project_memory_fails_safely_before_model_worker(
        self, stage, preflight
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "docs").mkdir()
            (root / "docs/architecture.md").write_bytes(
                b"## Current state\n\xffPRIVATE"
            )
            with self.assertRaises(TeamError) as error:
                answer_team("question", mode="direct", project=root)
        self.assertNotIn("PRIVATE", str(error.exception))
        stage.assert_not_called()

    def test_direct_and_review_provenance_are_based_on_completed_tasks(self):
        self.assertFalse(parse_events(events())["independent_critique_completed"])
        result = parse_events(events(["researcher", "answer-critic"]))
        self.assertTrue(result["independent_critique_completed"])
        self.assertEqual(["researcher", "answer-critic"], result["specialists"])

    def test_failed_partial_unknown_and_repeated_delegation_are_rejected(self):
        outputs = [
            events(["junior-developer"]),
            events(["answer-critic", "answer-critic"]),
            json.dumps(
                {"type": "error", "error": {"message": "private provider detail"}}
            ),
            json.dumps({"type": "text", "part": {"text": "unfinished"}}),
        ]
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(TeamError) as error:
                parse_events(output)
            self.assertNotIn("private provider detail", str(error.exception))

    def test_prompt_limits_and_modes(self):
        for args in (
            ("", "", "auto"),
            ("x" * 8001, "", "auto"),
            ("question", "x" * 24001, "auto"),
            ("question", "", "unsafe"),
            ("question", "", []),
        ):
            with self.assertRaises(TeamError):
                validate_request(*args)
        self.assertIsNone(validate_request("question", "evidence", "research"))

    def test_environment_drops_autoapprove_and_inline_overrides(self):
        with patch.dict(
            os.environ,
            {
                "OPENCODE_CONFIG_CONTENT": "unsafe",
                "OPENCODE_AUTO": "true",
                "OPENROUTER_API_KEY": "fake-test-key",
            },
        ):
            environment = clean_environment()
        self.assertNotIn("OPENCODE_AUTO", environment)
        self.assertEqual("fake-test-key", environment["OPENROUTER_API_KEY"])
        override = json.loads(environment["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual("deny", override["permission"]["webfetch"])
        self.assertEqual(
            "deny", override["agent"]["researcher"]["permission"]["webfetch"]
        )
        self.assertFalse(override["mcp"]["answer_team"]["enabled"])
        self.assertEqual(
            "deny",
            override["agent"]["answer-coordinator"]["permission"][
                "answer_team_ask_team"
            ],
        )

    @patch("scripts.answer_team.preflight")
    def test_credential_like_context_is_rejected_before_any_requests(self, preflight):
        token = "sk-or-v1-" + "x" * 40
        with self.assertRaises(TeamError) as error:
            answer_team("question", context=token)
        preflight.assert_not_called()
        self.assertNotIn(token, str(error.exception))

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_question_is_stdin_never_a_shell_argument(self, popen, native, preflight):
        process = popen.return_value.__enter__.return_value
        process.communicate.return_value = (events(), "private client log")
        process.returncode = 0
        question = "Explain this & echo shell-injection"
        result = answer_team(question, mode="direct")
        self.assertIn("answer", result)
        self.assertNotIn(question, popen.call_args.args[0])
        self.assertNotIn("--auto", popen.call_args.args[0])
        self.assertFalse(popen.call_args.kwargs.get("shell", False))
        self.assertIn(question, process.communicate.call_args.args[0])

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_failed_critic_stops_before_synthesis(self, stage, preflight):
        for mode, first in (
            ("review", "answer-coordinator"),
            ("consult", "researcher"),
        ):
            with self.subTest(mode=mode):
                stage.reset_mock()
                stage.side_effect = ["draft", TeamError("Critic unavailable")]
                with self.assertRaises(TeamError):
                    answer_team("question", mode=mode)
                self.assertEqual(
                    [first, "answer-critic"],
                    [call.args[0] for call in stage.call_args_list],
                )

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_controller_enforces_distinct_stages_and_passes_bounded_evidence(
        self, stage, preflight
    ):
        for mode, first in (
            ("auto", "answer-coordinator"),
            ("review", "answer-coordinator"),
            ("research", "researcher"),
        ):
            with self.subTest(mode=mode):
                stage.reset_mock()
                stage.side_effect = ["D" * 9000, "C" * 6000, "final"]
                result = answer_team("question", context="evidence", mode=mode)
                self.assertEqual(
                    [first, "answer-critic", "answer-coordinator"],
                    [call.args[0] for call in stage.call_args_list],
                )
                self.assertTrue(result["independent_critique_completed"])
                self.assertEqual(3, result["model_stages"])
                final_prompt = stage.call_args_list[-1].args[1]
                self.assertIn("evidence", final_prompt)
                self.assertTrue("D" * 9000 in final_prompt)
                self.assertTrue("C" * 5001 not in final_prompt)
                self.assertIn("Additional delivered draft text is unreviewed", final_prompt)

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_consult_preserves_draft_with_explicit_partial_review_for_parent_synthesis(
        self, stage, preflight
    ):
        stage.side_effect = ["D" * 9000, "C" * 6000]
        result = answer_team("question", mode="consult")
        self.assertEqual(
            ["researcher", "answer-critic"],
            [call.args[0] for call in stage.call_args_list],
        )
        self.assertNotIn("answer", result)
        self.assertEqual(9000, len(result["draft"]))
        self.assertEqual(5000, len(result["critique"]))
        self.assertIn("OMITTED MIDDLE", result["critique"])
        self.assertTrue(result["synthesis_required"])
        self.assertTrue(result["independent_critique_completed"])
        self.assertEqual(2, result["model_stages"])
        self.assertEqual({"draft": True, "critique": True}, result["truncation"])
        self.assertNotIn("D" * 8001, stage.call_args_list[1].args[1])

    def test_usage_is_observed_from_events_and_nonzero_cost_is_rejected(self):
        rows = [json.loads(line) for line in events().splitlines()]
        rows[-1]["part"].update(
            tokens={
                "input": 100,
                "output": 20,
                "reasoning": 5,
                "cache": {"read": 30, "write": 0},
            },
            cost=0,
        )
        usage = parse_events("\n".join(map(json.dumps, rows)))["usage"]
        self.assertEqual(100, usage["input_tokens"])
        self.assertEqual(30, usage["cache_read_tokens"])
        self.assertTrue(usage["token_counts_observed"])
        self.assertTrue(usage["cost_observed"])
        partial = [
            rows[0],
            rows[-1],
            {"type": "step_finish", "part": {"reason": "stop"}},
        ]
        partial_usage = parse_events("\n".join(map(json.dumps, partial)))["usage"]
        self.assertFalse(partial_usage["token_counts_observed"])
        self.assertEqual(1, partial_usage["steps_with_token_counts"])
        rows[-1]["part"]["cost"] = 0.01
        with self.assertRaises(TeamError):
            parse_events("\n".join(map(json.dumps, rows)))

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_worker_rejects_any_nested_delegation(self, popen, native, preflight):
        process = popen.return_value.__enter__.return_value
        process.communicate.return_value = (events(["answer-critic"]), "")
        process.returncode = 0
        with self.assertRaises(TeamError):
            answer_team("question", mode="direct")

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.stop_process")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_timeout_stops_owned_process_and_never_retries(
        self, popen, stop, native, preflight
    ):
        process = popen.return_value.__enter__.return_value
        process.communicate.side_effect = subprocess.TimeoutExpired("opencode", 10)
        with self.assertRaises(TeamError):
            answer_team("question", timeout=10)
        stop.assert_called_once_with(process)
        self.assertEqual(1, popen.call_count)

    def test_final_answer_combines_parts_without_old_commentary(self):
        rows = [
            {
                "type": "text",
                "part": {"messageID": "old", "id": "p1", "text": "Working..."},
            },
            {
                "type": "text",
                "part": {"messageID": "final", "id": "p2", "text": "Answer"},
            },
            {
                "type": "text",
                "part": {"messageID": "final", "id": "p3", "text": "Source"},
            },
            {"type": "step_finish", "part": {"reason": "stop"}},
        ]
        self.assertEqual(
            "Answer\n\nSource", parse_events("\n".join(map(json.dumps, rows)))["answer"]
        )
        with self.assertRaises(TeamError):
            parse_events(
                events()
                + "\n"
                + json.dumps({"type": "text", "part": {"text": "partial"}})
            )

    @patch("scripts.answer_team.answer_team")
    def test_mcp_only_exposes_answer_tool_and_restricts_arguments(self, run):
        init = rpc(
            {
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26"},
            },
            Path.cwd(),
        )
        self.assertEqual("2025-03-26", init["result"]["protocolVersion"])
        listing = rpc({"id": 2, "method": "tools/list"}, Path.cwd())
        self.assertEqual(["ask_team"], [t["name"] for t in listing["result"]["tools"]])
        run.return_value = {"answer": "answer", "specialists": []}
        result = rpc(
            {
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "ask_team",
                    "arguments": {"question": "q", "mode": "auto"},
                },
            },
            Path.cwd(),
        )
        self.assertFalse(result["result"]["isError"])
        self.assertEqual("consult", run.call_args.args[2])
        self.assertTrue(result["result"]["content"][0]["text"].startswith("answer\n\n"))
        self.assertNotIn("answer", result["result"]["structuredContent"])
        self.assertEqual(
            "content[0].text", result["result"]["structuredContent"]["answer_location"]
        )
        bad = rpc(
            {
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "ask_team",
                    "arguments": {"question": "q", "command": "arbitrary"},
                },
            },
            Path.cwd(),
        )
        self.assertTrue(bad["result"]["isError"])
        self.assertIsNone(rpc({"method": "notifications/initialized"}, Path.cwd()))

    def test_mcp_invalid_requests_are_protocol_errors(self):
        self.assertEqual(-32600, rpc([], Path.cwd())["error"]["code"])
        self.assertEqual(
            -32602,
            rpc({"id": 1, "method": "initialize", "params": []}, Path.cwd())["error"][
                "code"
            ],
        )


if __name__ == "__main__":
    unittest.main()

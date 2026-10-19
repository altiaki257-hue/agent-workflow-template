"""Evaluation boundaries: no implicit inference, misleading drafts, or leaked errors."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import promptfoo_provider as provider
from scripts import run_promptfoo as runner


class PromptfooBoundaryTests(unittest.TestCase):
    def test_offline_default_never_calls_controller(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(provider, "answer_team") as call,
        ):
            result = provider.call_api(
                "Synthetic question",
                {},
                {"vars": {"fixture_output": "Synthetic answer"}},
            )
        call.assert_not_called()
        self.assertEqual(result["output"], "Synthetic answer")
        self.assertEqual(result["metadata"]["execution"], "offline_fixture")

    def test_missing_fixture_is_error_without_implicit_live_fallback(self):
        with (
            patch.dict(os.environ, {"ANSWER_EVAL_LIVE": "0"}),
            patch.object(provider, "answer_team") as call,
        ):
            result = provider.call_api("Question", {}, {})
        call.assert_not_called()
        self.assertIn("error", result)

    def test_consult_drafts_cannot_be_selected_for_grading(self):
        with patch.object(provider, "answer_team") as call:
            result = provider.call_api("Question", {"config": {"route": "consult"}}, {})
        call.assert_not_called()
        self.assertIn("error", result)

    def test_live_reuses_guarded_controller_with_supplied_scope(self):
        with (
            patch.dict(os.environ, {"ANSWER_EVAL_LIVE": "1"}),
            patch.object(
                provider,
                "answer_team",
                return_value={"answer": "Final answer", "usage": None},
            ) as call,
        ):
            result = provider.call_api(
                "Question",
                {"config": {"route": "review"}},
                {"vars": {"evidence": "Facts"}},
            )
        call.assert_called_once_with(
            "Question", "Facts", "review", provider.ROOT, evidence_scope="supplied"
        )
        self.assertEqual(result["output"], "Final answer")
        self.assertIsNone(result["metadata"]["usage"])
        self.assertNotIn("cost", result)
        self.assertNotIn("tokenUsage", result)

    def test_unsynthesized_result_and_raw_errors_are_not_exposed(self):
        for response in (
            {"draft": "Draft", "synthesis_required": True},
            provider.TeamError("private error details"),
            OSError("private local details"),
        ):
            with (
                self.subTest(response=type(response).__name__),
                patch.dict(os.environ, {"ANSWER_EVAL_LIVE": "1"}),
                patch.object(provider, "answer_team") as call,
            ):
                if isinstance(response, Exception):
                    call.side_effect = response
                else:
                    call.return_value = response
                result = provider.call_api("Question", {}, {})
            self.assertIn("error", result)
            self.assertNotIn("private", result["error"])
            self.assertNotIn("output", result)

    def test_runner_overrides_inherited_live_flag_and_disables_upload_features(self):
        with patch.dict(os.environ, {"ANSWER_EVAL_LIVE": "1"}):
            environment = runner.evaluation_environment()
        self.assertEqual(environment["ANSWER_EVAL_LIVE"], "0")
        self.assertEqual(environment["PROMPTFOO_DISABLE_TELEMETRY"], "1")
        self.assertEqual(environment["PROMPTFOO_DISABLE_REMOTE_GENERATION"], "true")

    def test_runner_rejects_repository_output_before_starting_subprocess(self):
        with (
            patch(
                "sys.argv", ["run_promptfoo", "--output", str(runner.ROOT / "raw.json")]
            ),
            patch.object(runner.subprocess, "run") as call,
        ):
            with self.assertRaises(SystemExit):
                runner.main()
        call.assert_not_called()

    def test_external_output_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "synthetic.json"
            self.assertEqual(runner.output_path(destination), destination.resolve())

    def test_windows_launcher_uses_node_without_a_command_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            entry = base / "node_modules/promptfoo/dist/src/entrypoint.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("// Synthetic fixture", encoding="utf-8")
            commands = {
                "promptfoo.cmd": str(base / "promptfoo.cmd"),
                "node": "node.exe",
            }
            with (
                patch.object(runner, "os", SimpleNamespace(name="nt")),
                patch.object(runner.shutil, "which", side_effect=commands.get),
            ):
                self.assertEqual(runner.promptfoo_command(), ["node.exe", str(entry)])

    def test_runner_does_not_forward_shell_metacharacters_through_a_shim(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "literal & evaluation.json"
            with (
                patch("sys.argv", ["run_promptfoo", "--output", str(destination)]),
                patch.object(
                    runner,
                    "promptfoo_command",
                    return_value=["node.exe", "entrypoint.js"],
                ),
                patch.object(runner.subprocess, "run") as call,
            ):
                call.side_effect = [
                    SimpleNamespace(stdout=runner.PROMPTFOO_VERSION),
                    SimpleNamespace(returncode=0),
                ]
                self.assertEqual(runner.main(), 0)
            args, kwargs = call.call_args
            self.assertEqual(args[0][:2], ["node.exe", "entrypoint.js"])
            self.assertIn(str(destination.resolve()), args[0])
            self.assertNotIn("shell", kwargs)


if __name__ == "__main__":
    unittest.main()

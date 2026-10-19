import json
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from scripts import answer_team as controller


class TelemetryDispatchTests(unittest.TestCase):
    def test_disabled_path_imports_no_sdk_and_launches_nothing(self):
        with (
            patch.dict(os.environ, {"ANSWER_TEAM_LANGFUSE": "0"}),
            patch.dict(sys.modules, {"langfuse": None}),
            patch.object(controller.subprocess, "Popen") as launch,
        ):
            controller.schedule_telemetry({"answer": "PRIVATE"}, "direct")
        launch.assert_not_called()

    def test_exporter_environment_and_worker_credentials_are_separated(self):
        environment = {
            "ANSWER_TEAM_LANGFUSE": "1",
            "LANGFUSE_PUBLIC_KEY": "synthetic-public",
            "LANGFUSE_SECRET_KEY": "synthetic-secret",
            "LANGFUSE_BASE_URL": "https://example.invalid",
            "LANGFUSE_HOST": "https://example.invalid",
            "GROQ_API_KEY": "PRIVATE",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "PRIVATE",
            "PATH": "synthetic-path",
        }
        with patch.dict(os.environ, environment, clear=True):
            child = controller.telemetry_environment()
            worker = controller.clean_environment()
        self.assertNotIn("PRIVATE", json.dumps(child))
        self.assertEqual(
            "false", child["LANGFUSE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED"]
        )
        self.assertFalse(
            any(name.startswith(("LANGFUSE_", "OTEL_")) for name in worker)
        )
        self.assertNotIn("ANSWER_TEAM_LANGFUSE", worker)
        self.assertEqual("PRIVATE", worker["GROQ_API_KEY"])

    def test_dispatch_sanitizes_file_input_and_waits_only_in_background(self):
        captured = {}
        process = Mock()

        def launch(*args, **kwargs):
            captured.update(kwargs)
            captured["payload"] = json.loads(kwargs["stdin"].read())
            return process

        with (
            patch.object(
                controller,
                "telemetry_environment",
                return_value={"ANSWER_TEAM_LANGFUSE": "1"},
            ),
            patch.object(controller.subprocess, "Popen", side_effect=launch),
            patch.object(controller.threading, "Thread") as thread,
        ):
            controller.schedule_telemetry(
                {
                    "answer": "PRIVATE",
                    "error": "PRIVATE",
                    "evidence_scope": "supplied",
                    "status": "completed",
                },
                "direct",
            )
        self.assertNotIn("PRIVATE", json.dumps(captured["payload"]))
        self.assertEqual("completed", captured["payload"]["status"])
        self.assertEqual(subprocess.DEVNULL, captured["stdout"])
        self.assertEqual(subprocess.DEVNULL, captured["stderr"])
        process.wait.assert_not_called()
        thread.return_value.start.assert_called_once()
        process.wait.side_effect = [subprocess.TimeoutExpired("exporter", 15), 0]
        thread.call_args.kwargs["target"]()
        process.kill.assert_called_once()

    def test_telemetry_failure_does_not_replace_answer(self):
        answer = {"answer": "Correct answer", "evidence_scope": "supplied"}
        with (
            patch.object(controller, "_answer_team", return_value=answer),
            patch.object(
                controller,
                "telemetry_environment",
                return_value={"ANSWER_TEAM_LANGFUSE": "1"},
            ),
            patch.object(
                controller.subprocess, "Popen", side_effect=OSError("PRIVATE")
            ),
        ):
            self.assertIs(
                answer, controller.answer_team("Question", evidence_scope="supplied")
            )

    def test_failed_answer_exports_no_question_context_or_exception_text(self):
        with (
            patch.object(
                controller, "_answer_team", side_effect=controller.TeamError("PRIVATE")
            ),
            patch.object(controller, "schedule_telemetry") as export,
        ):
            with self.assertRaises(controller.TeamError):
                controller.answer_team(
                    "PRIVATE QUESTION", "PRIVATE CONTEXT", evidence_scope="supplied"
                )
        self.assertNotIn("PRIVATE", json.dumps(export.call_args.args[0]))
        self.assertEqual("failed", export.call_args.args[0]["status"])
        self.assertNotIn("usage", export.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

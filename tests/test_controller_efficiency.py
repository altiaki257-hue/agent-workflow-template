import copy
import json
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from scripts import answer_team as controller
from scripts.validate_repo import ROOT


MODEL = "openrouter/cohere/north-mini-code:free"
CATALOG = {
    "data": [
        {
            "id": MODEL.removeprefix("openrouter/"),
            "pricing": {"prompt": "0", "completion": "0"},
            "supported_parameters": ["tools"],
        }
    ]
}


def events(parts):
    rows = [{"type": "text", "part": {"text": "synthetic final answer"}}]
    rows += [
        {"type": "step_finish", "part": {"reason": "stop", **part}} for part in parts
    ]
    return "\n".join(map(json.dumps, rows))


class ControllerEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
        self.addCleanup(patch.stopall)
        patch("scripts.answer_team.CATALOG", None).start()
        patch("scripts.answer_team.CATALOG_AT", 0).start()

    def debug_results(self):
        return [
            SimpleNamespace(stdout=json.dumps(self.config)),
            SimpleNamespace(
                stdout=json.dumps(
                    {
                        "permission": [
                            {"permission": "read", "pattern": "*", "action": "deny"}
                        ]
                    }
                )
            ),
        ]

    @patch("scripts.answer_team.urlopen", side_effect=OSError("catalog unavailable"))
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.run")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_direct_model_needs_no_router_and_worker_helpers_use_same_model(
        self, popen, debug, native, catalog
    ):
        debug.side_effect = self.debug_results()
        process = popen.return_value.__enter__.return_value
        process.communicate.return_value = (
            events([{"tokens": {"input": 10, "output": 4}, "cost": 0.001}]),
            "",
        )
        process.returncode = 0
        with patch(
            "scripts.answer_team.approved_environment",
            side_effect=lambda model, env: env,
        ):
            result = controller.answer_team(
                "synthetic question", mode="direct", project=ROOT
            )
        self.assertEqual("synthetic final answer", result["answer"])
        catalog.assert_not_called()
        self.assertEqual(2, debug.call_count)
        model = popen.call_args.args[0][popen.call_args.args[0].index("--model") + 1]
        override = json.loads(popen.call_args.kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual("groq/openai/gpt-oss-120b", model)
        self.assertEqual(model, override["model"])
        self.assertEqual(model, override["small_model"])
        self.assertEqual(model, override["agent"]["answer-coordinator"]["model"])
        self.assertFalse(override["mcp"]["answer_team"]["enabled"])
        self.assertFalse(result["usage"]["token_counts_observed"])
        self.assertTrue(result["usage"]["token_fields_observed"]["input_tokens"])

    @patch("scripts.answer_team.urlopen")
    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.run")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_actual_router_backup_checks_only_its_target(
        self, popen, debug, native, catalog
    ):
        debug.side_effect = self.debug_results()
        process = popen.return_value.__enter__.return_value
        process.communicate.side_effect = [
            (json.dumps({"type": "error", "error": {"data": {"statusCode": 429}}}), ""),
            (events([{"cost": 0}]), ""),
        ]
        process.returncode = 0
        catalog.return_value.__enter__.return_value.read.return_value = json.dumps(
            CATALOG
        ).encode()
        with patch(
            "scripts.answer_team.approved_environment",
            side_effect=lambda model, env: env,
        ):
            result = controller.answer_team(
                "synthetic question", mode="direct", project=ROOT
            )
        self.assertEqual(MODEL, result["stages"][0]["model"])
        self.assertEqual(2, len(result["stages"][0]["attempts"]))
        catalog.assert_called_once()
        self.assertEqual(2, popen.call_count)
        # All four unused manual endpoints are absent from this catalog.
        self.assertTrue(result["stages"][0]["attempts"][0]["usage_unknown"])

    @patch("scripts.answer_team.urlopen")
    def test_selected_router_rejects_bad_metadata_and_does_not_reuse_other_model_approval(
        self, fetch
    ):
        fetch.return_value.__enter__.return_value.read.return_value = json.dumps(
            CATALOG
        ).encode()
        deadline = controller.time.monotonic() + 30
        controller.verify_model(MODEL, ROOT, deadline)
        controller.verify_model(MODEL, ROOT, deadline)
        fetch.assert_called_once()
        for catalog in (
            {"data": []},
            {
                "data": [
                    {
                        **CATALOG["data"][0],
                        "pricing": {"prompt": "1", "completion": "0"},
                    }
                ]
            },
            {"data": [{**CATALOG["data"][0], "supported_parameters": []}]},
            {
                "data": [
                    {
                        **CATALOG["data"][0],
                        "expiration_date": (
                            date.today() + timedelta(days=7)
                        ).isoformat(),
                    }
                ]
            },
        ):
            with (
                self.subTest(catalog=catalog),
                patch("scripts.answer_team.CATALOG", catalog),
            ):
                with self.assertRaises(controller.TeamError):
                    controller.verify_model(MODEL, ROOT, deadline)
        with self.assertRaises(controller.TeamError):
            controller.verify_model(
                "openrouter/nvidia/nemotron-3-super-120b-a12b:free", ROOT, deadline
            )
        with self.assertRaises(controller.TeamError):
            controller.verify_model("openrouter/unreviewed-model:free", ROOT, deadline)
        fetch.assert_called_once()

    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.run")
    def test_preflight_consumes_one_deadline_and_stops_before_expired_probe(
        self, debug, native
    ):
        clock = {"now": 0}
        outputs = self.debug_results()

        def probe(*args, **kwargs):
            clock["now"] += 8 if debug.call_count == 1 else 1
            return outputs[debug.call_count - 1]

        debug.side_effect = probe
        with patch(
            "scripts.answer_team.time.monotonic", side_effect=lambda: clock["now"]
        ):
            controller.preflight(ROOT, deadline=10)
        self.assertEqual(
            [10, 2], [call.kwargs["timeout"] for call in debug.call_args_list]
        )
        debug.reset_mock()
        clock["now"] = 0

        def exhaust(*args, **kwargs):
            clock["now"] = 10
            return outputs[0]

        debug.side_effect = exhaust
        with patch(
            "scripts.answer_team.time.monotonic", side_effect=lambda: clock["now"]
        ):
            with self.assertRaises(controller.TeamError):
                controller.preflight(ROOT, deadline=10)
        debug.assert_called_once()

    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.run")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_merged_permission_changes_still_stop_before_any_inference(
        self, popen, debug, native
    ):
        effective = copy.deepcopy(self.config)
        effective["permission"]["edit"] = "allow"
        debug.side_effect = [
            SimpleNamespace(stdout=json.dumps(effective)),
            self.debug_results()[1],
        ]
        with self.assertRaises(controller.TeamError):
            controller.answer_team("synthetic question", mode="direct", project=ROOT)
        popen.assert_not_called()

    @patch("scripts.answer_team.urlopen", side_effect=OSError("unavailable"))
    @patch("scripts.answer_team.subprocess.Popen")
    def test_router_catalog_failure_stops_before_worker(self, popen, fetch):
        with self.assertRaises(controller.TeamError):
            controller.run_stage(
                "answer-coordinator",
                "synthetic",
                ROOT,
                10,
                exclude_models=("groq/openai/gpt-oss-120b",),
            )
        fetch.assert_called_once()
        popen.assert_not_called()

    @patch("scripts.answer_team.urlopen")
    def test_catalog_timeout_uses_remaining_stage_budget(self, fetch):
        fetch.return_value.__enter__.return_value.read.return_value = json.dumps(
            CATALOG
        ).encode()
        with patch("scripts.answer_team.time.monotonic", return_value=9):
            controller.verify_model(MODEL, ROOT, deadline=10)
        self.assertEqual(1, fetch.call_args.kwargs["timeout"])
        fetch.reset_mock()
        with patch("scripts.answer_team.time.monotonic", return_value=10):
            with self.assertRaises(controller.TeamError):
                controller.verify_model(MODEL, ROOT, deadline=10)
        fetch.assert_not_called()

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_stage")
    def test_each_required_stage_gets_time_and_unused_time_carries_forward(
        self, stage, preflight
    ):
        clock = {"now": 0}
        allowances = []

        def run(agent, prompt, project, timeout, metrics, **kwargs):
            allowances.append(timeout)
            clock["now"] += 10
            return "synthetic answer"

        stage.side_effect = run
        with patch(
            "scripts.answer_team.time.monotonic", side_effect=lambda: clock["now"]
        ):
            result = controller.answer_team(
                "synthetic question", mode="review", project=ROOT, timeout=120
            )
        self.assertEqual([40, 55, 100], allowances)
        self.assertTrue(result["independent_critique_completed"])
        self.assertEqual(3, stage.call_count)
        self.assertEqual(120, preflight.call_args.args[1])

    def test_missing_telemetry_preserves_observed_subtotals_and_completeness(self):
        for tokens in (
            {},
            {"input": 20},
            {"output": 5},
            {"cache": {"read": 0}},
            {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0}},
        ):
            with self.subTest(tokens=tokens):
                usage = controller.parse_events(events([{"tokens": tokens}]))["usage"]
                self.assertFalse(usage["token_counts_observed"])
                self.assertFalse(usage["cost_observed"])
                self.assertEqual(tokens.get("input", 0), usage["input_tokens"])
                self.assertEqual(
                    "input" in tokens, usage["token_fields_observed"]["input_tokens"]
                )
        full = {
            "input": 0,
            "output": 0,
            "reasoning": 0,
            "cache": {"read": 0, "write": 0},
        }
        usage = controller.parse_events(events([{"tokens": full, "cost": 0}]))["usage"]
        self.assertTrue(usage["token_counts_observed"])
        self.assertTrue(usage["cost_observed"])
        partial = controller.parse_events(
            events([{"tokens": {**full, "input": 10}}, {"tokens": {"input": 5}}])
        )["usage"]
        self.assertEqual(15, partial["input_tokens"])
        self.assertEqual(1, partial["steps_with_token_counts"])
        self.assertTrue(partial["token_fields_observed"]["input_tokens"])
        self.assertFalse(partial["token_fields_observed"]["output_tokens"])

    @patch("scripts.answer_team.preflight")
    @patch("scripts.answer_team.run_attempt")
    def test_multi_stage_telemetry_does_not_hide_missing_fields(
        self, attempt, preflight
    ):
        partial = controller.parse_events(
            events([{"tokens": {"input": 7, "output": 2}, "cost": 0}])
        )
        full = controller.parse_events(
            events(
                [
                    {
                        "tokens": {
                            "input": 10,
                            "output": 3,
                            "reasoning": 0,
                            "cache": {"read": 0, "write": 0},
                        },
                        "cost": 0,
                    }
                ]
            )
        )
        attempt.side_effect = [(partial, 0.1), (full, 0.1)]
        result = controller.answer_team("synthetic", mode="consult", project=ROOT)
        self.assertEqual(17, result["usage"]["input_tokens"])
        self.assertEqual(5, result["usage"]["output_tokens"])
        self.assertTrue(result["usage"]["token_fields_observed"]["input_tokens"])
        self.assertFalse(result["usage"]["token_fields_observed"]["cache_read_tokens"])
        self.assertFalse(result["usage"]["token_counts_observed"])
        self.assertTrue(result["usage"]["cost_observed"])

    @patch("scripts.answer_team.native_opencode", return_value="opencode.exe")
    @patch("scripts.answer_team.subprocess.Popen")
    def test_expired_attempt_cannot_start_worker_after_credential_check(
        self, popen, native
    ):
        clock = {"now": 0}

        def slow_confirmation(model, env):
            clock["now"] = 11
            return env

        with (
            patch(
                "scripts.answer_team.time.monotonic", side_effect=lambda: clock["now"]
            ),
            patch(
                "scripts.answer_team.approved_environment",
                side_effect=slow_confirmation,
            ),
        ):
            with self.assertRaises(controller.TeamError):
                controller.run_attempt(
                    "answer-coordinator",
                    "synthetic",
                    ROOT,
                    10,
                    "groq/openai/gpt-oss-120b",
                )
        popen.assert_not_called()

    def test_invalid_telemetry_vetoes_transient_errors_even_for_free_accounts(self):
        for part in (
            {"tokens": {"input": True}},
            {"tokens": {"output": float("nan")}},
            {"tokens": {"cache": {"read": float("inf")}}},
            {"cost": True},
            {"cost": -1},
            {"cost": float("inf")},
            {"tokens": []},
            {"tokens": {"cache": []}},
        ):
            for order in (False, True):
                first = events([part])
                transient = json.dumps(
                    {"type": "error", "error": {"data": {"statusCode": 429}}}
                )
                output = first + "\n" + transient if order else transient + "\n" + first
                with (
                    self.subTest(part=part, order=order),
                    self.assertRaises(controller.TeamError) as error,
                ):
                    controller.parse_events(output, account_tier=True)
                self.assertNotIsInstance(error.exception, controller.AvailabilityError)

    @patch("scripts.answer_team.answer_team")
    def test_mcp_prose_once_text_clients_keep_synthesis_notices_and_metadata_is_not_mutated(
        self, run
    ):
        for result in (
            {"answer": "UNIQUE_FINAL", "specialists": []},
            {
                "draft": "UNIQUE_DRAFT",
                "critique": "UNIQUE_CRITIQUE",
                "synthesis_required": True,
                "specialists": ["researcher", "answer-critic"],
                "independent_critique_completed": True,
                "model_stages": 2,
                "truncation": {"draft": True, "critique": False},
            },
        ):
            run.return_value = copy.deepcopy(result)
            response = controller.rpc(
                {
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "ask_team",
                        "arguments": {"question": "synthetic"},
                    },
                },
                ROOT,
            )["result"]
            wire = json.dumps(response)
            for field in ("answer", "draft", "critique"):
                if field in result:
                    self.assertEqual(1, wire.count(result[field]))
                    self.assertNotIn(field, response["structuredContent"])
            self.assertEqual(
                "content[0].text", response["structuredContent"]["answer_location"]
            )
            self.assertEqual(result, run.return_value)
            if result.get("synthesis_required"):
                text = response["content"][0]["text"]
                self.assertIn("synthesize", text)
                self.assertIn("truncated", text)
                self.assertTrue(response["structuredContent"]["synthesis_required"])
                self.assertTrue(
                    response["structuredContent"]["independent_critique_completed"]
                )


if __name__ == "__main__":
    unittest.main()

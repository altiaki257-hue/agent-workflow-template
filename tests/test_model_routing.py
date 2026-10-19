import copy
import hashlib
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.answer_team import (
    AvailabilityError,
    TeamError,
    parse_events,
    provider_error,
    run_stage,
)
from scripts.model_routing import RoutingError, approved_environment, candidates
from scripts.validate_repo import ROLE_MODELS, ROOT, config_errors


class ModelRoutingTests(unittest.TestCase):
    def setUp(self):
        # Routing unit tests never access a live catalog; JIT integration has its own cases.
        catalog = patch("scripts.answer_team.verify_model")
        catalog.start()
        self.addCleanup(catalog.stop)

    def test_owner_confirmation_is_key_bound_fresh_and_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "confirmation.json"
            good = {
                "groq": {
                    "free_tier": True,
                    "paid_billing_disabled": True,
                    "confirmed_on": date.today().isoformat(),
                    "key_sha256": hashlib.sha256(b"synthetic-key").hexdigest(),
                }
            }
            with patch(
                "scripts.model_routing.credential", return_value="synthetic-key"
            ):
                for field, value in (
                    ("free_tier", False),
                    ("paid_billing_disabled", False),
                    ("key_sha256", "changed-key"),
                    ("confirmed_on", (date.today() - timedelta(days=31)).isoformat()),
                    ("confirmed_on", (date.today() + timedelta(days=1)).isoformat()),
                ):
                    bad = copy.deepcopy(good)
                    bad["groq"][field] = value
                    path.write_text(json.dumps(bad))
                    with self.assertRaises(RoutingError):
                        approved_environment("groq/openai/gpt-oss-120b", {}, path)
                path.write_text(json.dumps(good))
                result = approved_environment(
                    "groq/openai/gpt-oss-120b", {"KEEP": "yes"}, path
                )
                self.assertEqual("synthetic-key", result["GROQ_API_KEY"])
                self.assertEqual("yes", result["KEEP"])
                path.unlink()
                with self.assertRaises(RoutingError):
                    approved_environment("groq/openai/gpt-oss-120b", {}, path)

    def test_only_structured_transient_statuses_allow_backup(self):
        for status in (429, 500, 502, 503, 504):
            with self.assertRaises(AvailabilityError):
                provider_error({"error": {"data": {"statusCode": status}}})
        for data in (
            {},
            {"statusCode": 401},
            {"statusCode": 403},
            {"statusCode": 400},
            {"statusCode": "429"},
            {"message": "429 private detail"},
        ):
            with self.assertRaises(TeamError) as error:
                provider_error({"error": {"data": data}})
            self.assertNotIsInstance(error.exception, AvailabilityError)
            self.assertNotIn("private", str(error.exception))

    def test_auth_and_unknown_errors_veto_transient_errors_in_either_order(self):
        for statuses in ((429, 401), (401, 429), (503, 400), (429, None)):
            output = "\n".join(
                json.dumps({"type": "error", "error": {"data": {"statusCode": status}}})
                for status in statuses
            )
            with self.assertRaises(TeamError) as error:
                parse_events(output)
            self.assertNotIsInstance(error.exception, AvailabilityError)

    def test_partial_policy_evidence_vetoes_availability_fallback(self):
        transient = {"type": "error", "error": {"data": {"statusCode": 429}}}
        for policy_event in (
            {"type": "step_finish", "part": {"cost": 0.01}},
            {"type": "step_finish", "part": {"cost": -1}},
            {"type": "step_finish", "part": {"tokens": {"input": -1}}},
            {"type": "tool_use", "part": {"tool": "task"}},
        ):
            for events in ((transient, policy_event), (policy_event, transient)):
                with self.assertRaises(TeamError) as error:
                    parse_events("\n".join(map(json.dumps, events)), worker=True)
                self.assertNotIsInstance(error.exception, AvailabilityError)

    @patch("scripts.answer_team.run_attempt")
    def test_one_exact_backup_records_provenance_and_never_loops(self, attempt):
        success = ({"answer": "answer", "usage": {}}, 0.1)
        attempt.side_effect = [AvailabilityError("unavailable"), success]
        metrics = []
        self.assertEqual(
            "answer", run_stage("researcher", "synthetic", Path.cwd(), 10, metrics)
        )
        self.assertEqual(
            list(candidates("researcher")),
            [call.args[-1] for call in attempt.call_args_list],
        )
        self.assertEqual(candidates("researcher")[1], metrics[0]["model"])
        self.assertTrue(metrics[0]["attempts"][0]["usage_unknown"])
        attempt.reset_mock()
        attempt.side_effect = AvailabilityError("unavailable")
        with self.assertRaises(TeamError):
            run_stage("researcher", "synthetic", Path.cwd(), 10)
        self.assertEqual(2, attempt.call_count)

    @patch("scripts.answer_team.run_attempt")
    def test_auth_policy_and_unknown_errors_never_fall_back(self, attempt):
        for error in (
            TeamError("authentication"),
            TeamError("policy"),
            OSError("local"),
        ):
            attempt.reset_mock()
            attempt.side_effect = error
            with self.assertRaises((TeamError, OSError)):
                run_stage("researcher", "synthetic", Path.cwd(), 10)
            attempt.assert_called_once()

    @patch("scripts.answer_team.run_attempt")
    def test_critic_never_uses_actual_draft_model_including_backup(self, attempt):
        primary, backup = candidates("answer-critic")
        attempt.return_value = ({"answer": "review", "usage": {}}, 0.1)
        run_stage(
            "answer-critic", "synthetic", Path.cwd(), 10, exclude_models=(primary,)
        )
        self.assertEqual(backup, attempt.call_args.args[-1])
        attempt.reset_mock()
        attempt.side_effect = AvailabilityError("unavailable")
        with self.assertRaises(TeamError):
            run_stage(
                "answer-critic", "synthetic", Path.cwd(), 10, exclude_models=(backup,)
            )
        self.assertEqual(1, attempt.call_count)
        attempt.reset_mock()
        with self.assertRaises(TeamError):
            run_stage(
                "answer-critic",
                "synthetic",
                Path.cwd(),
                10,
                exclude_models=(primary, backup),
            )
        attempt.assert_not_called()

    @patch("scripts.answer_team.run_attempt")
    def test_backup_shares_original_deadline(self, attempt):
        attempt.side_effect = AvailabilityError("unavailable")
        with patch("scripts.answer_team.time.monotonic", side_effect=[0, 0, 0, 11]):
            with self.assertRaises(TeamError):
                run_stage("researcher", "synthetic", Path.cwd(), 10)
        attempt.assert_called_once()

    def test_account_catalog_estimate_is_not_relabelled_zero_or_billing(self):
        events = "\n".join(
            map(
                json.dumps,
                [
                    {"type": "text", "part": {"text": "answer"}},
                    {"type": "step_finish", "part": {"reason": "stop", "cost": 0.005}},
                ],
            )
        )
        with self.assertRaises(TeamError):
            parse_events(events)
        self.assertEqual(
            0.005, parse_events(events, account_tier=True)["usage"]["reported_cost_usd"]
        )

    def test_role_models_backups_and_permissions_remain_reviewed(self):
        config = json.loads((ROOT / "opencode.json").read_text(encoding="utf8"))
        self.assertFalse(config_errors(config))
        for role, (primary, backup) in ROLE_MODELS.items():
            self.assertNotEqual(primary, backup)
            self.assertEqual(primary, config["agent"][role]["model"])
            command = (ROOT / f".opencode/commands/{role}-backup.md").read_text(
                encoding="utf8"
            )
            self.assertIn(f"agent: {role}\nmodel: {backup}\n", command)
            bad = copy.deepcopy(config)
            bad["agent"][role]["model"] = "groq/paid-unreviewed-model"
            self.assertTrue(config_errors(bad))
        with self.assertRaises(RoutingError):
            candidates("arbitrary-implementer")


if __name__ == "__main__":
    unittest.main()

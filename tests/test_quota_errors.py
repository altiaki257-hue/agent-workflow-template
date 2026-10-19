import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.answer_team import (
    AvailabilityError,
    TeamError,
    parse_events,
    provider_error,
    run_stage,
)


def provider_event(body=None, **metadata):
    data = {"statusCode": 429, **metadata}
    if body is not None:
        data["responseBody"] = json.dumps(body)
    return {"type": "error", "error": {"name": "APIError", "data": data}}


class QuotaErrorTests(unittest.TestCase):
    def assert_terminal(self, event):
        with self.assertRaises(TeamError) as caught:
            provider_error(event)
        self.assertNotIsInstance(caught.exception, AvailabilityError)
        return str(caught.exception)

    def test_documented_terminal_codes_and_type_stop_even_if_retryable(self):
        for field, code in (
            ("code", "credit_balance_exhausted"),
            ("code", "organization_spend_limit_exceeded"),
            ("code", "project_spend_limit_exceeded"),
            ("code", "organization_usage_limit_exceeded"),
            ("type", "insufficient_quota"),
            ("code", "insufficient_quota"),
        ):
            with self.subTest(field=field, code=code):
                self.assert_terminal(
                    provider_event({"error": {field: code}}, isRetryable=True)
                )
        self.assert_terminal(
            provider_event(
                {"error": {"code": 429, "metadata": {"error_type": "payment_required"}}}
            )
        )

    def test_explicit_native_nonretryable_429_stops_without_quota_claim(self):
        message = self.assert_terminal(provider_event(isRetryable=False))
        self.assertIn("non-retryable", message)
        self.assertNotIn("quota", message)

    def test_temporary_limits_and_prose_do_not_establish_terminal_quota(self):
        for event in (
            provider_event(),
            provider_event(isRetryable=True),
            provider_event({"error": {"status": "RESOURCE_EXHAUSTED", "code": 429}}),
            provider_event({"error": {"type": "rate_limit_exceeded"}}),
            provider_event(
                {"error": {"code": 429, "metadata": {"error_type": "rate_limit_exceeded"}}}
            ),
            provider_event({"error": {"message": "insufficient_quota private prose"}}),
            provider_event(message="credit_balance_exhausted private prose"),
            provider_event(statusCode=503, isRetryable=False),
        ):
            with self.subTest(event=event), self.assertRaises(AvailabilityError):
                provider_error(event)

    def test_malformed_or_oversized_metadata_fails_safely(self):
        for metadata in (
            {"isRetryable": "false"},
            {"isRetryable": 0},
            {"responseBody": 1},
            {"responseBody": "not JSON"},
            {"responseBody": "x" * 16001},
            {"responseBody": "[" * 1200 + "]" * 1200},
        ):
            with self.subTest(metadata_type=tuple(metadata)):
                self.assert_terminal(provider_event(**metadata))
        for body in (
            [],
            {"error": "private upstream detail"},
            {"error": {"code": []}},
            {"error": {"type": True}},
            {"error": {"type": 429}},
            {"error": {"metadata": []}},
            {"error": {"metadata": {"error_type": 1}}},
        ):
            with self.subTest(body=body):
                self.assert_terminal(provider_event(body))

    def test_terminal_error_redacts_body_and_metadata(self):
        message = self.assert_terminal(
            provider_event(
                {
                    "error": {
                        "code": "credit_balance_exhausted",
                        "message": "PRIVATE-UPSTREAM-DETAIL",
                    }
                },
                message="PRIVATE-METADATA-DETAIL",
            )
        )
        self.assertNotIn("PRIVATE", message)
        self.assertNotIn("credit_balance_exhausted", message)

    def test_terminal_event_vetoes_availability_in_either_order(self):
        transient = provider_event()
        terminal = provider_event({"error": {"type": "insufficient_quota"}})
        for events in ((transient, terminal), (terminal, transient)):
            with self.subTest(events=events), self.assertRaises(TeamError) as caught:
                parse_events("\n".join(map(json.dumps, events)))
            self.assertNotIsInstance(caught.exception, AvailabilityError)

    @patch("scripts.answer_team.verify_model")
    @patch("scripts.answer_team.run_attempt")
    def test_terminal_quota_starts_no_backup(self, attempt, verify):
        attempt.side_effect = lambda *args, **kwargs: provider_error(
            provider_event({"error": {"type": "insufficient_quota"}})
        )
        with self.assertRaises(TeamError) as caught:
            run_stage("researcher", "Synthetic question", Path.cwd(), 10)
        self.assertNotIsInstance(caught.exception, AvailabilityError)
        attempt.assert_called_once()
        verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()

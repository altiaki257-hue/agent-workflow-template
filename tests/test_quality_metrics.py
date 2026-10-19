"""Measurement failures and incomplete audits must never become clean reports."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import quality_metrics as metrics
from scripts import answer_team as controller
from scripts import check_provider_access as access
from scripts.model_routing import RoutingError, approved_environment


class QualityMeasurementTests(unittest.TestCase):
    def test_incomplete_and_empty_dependency_reports_are_rejected(self):
        for report in (
            [],
            {},
            {"dependencies": []},
            {"dependencies": [None]},
            {"dependencies": [{}]},
            {"dependencies": [{"name": "x", "version": "1"}]},
            {"dependencies": [{"name": "x", "version": "1", "vulns": [{}]}]},
            {"dependencies": [{"name": "unknown", "skip_reason": "unavailable"}]},
        ):
            with self.subTest(report=report), self.assertRaises(ValueError):
                metrics.summarize_audit(report)

    def test_audit_summary_bounds_output_without_hiding_finding_count(self):
        report = {
            "dependencies": [
                {
                    "name": f"package{i}",
                    "version": "1",
                    "vulns": [{"id": f"CVE-{i}", "description": "Private long output"}],
                }
                for i in range(14)
            ]
        }
        summary = metrics.summarize_audit(report)
        self.assertEqual(14, summary["vulnerable_packages"])
        self.assertEqual(10, len(summary["findings"]))
        self.assertEqual(4, summary["additional_findings"])
        self.assertNotIn("Private", json.dumps(summary))

    def test_reports_cannot_overwrite_existing_data_or_enter_git(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            note = output / "keep.md"
            note.write_text("Owner data", encoding="utf-8")
            with self.assertRaises(ValueError):
                metrics.measure("coverage", output)
            self.assertEqual("Owner data", note.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            metrics.measure("coverage", metrics.ROOT / "reports")

    def test_failed_tests_cannot_be_reported_as_passing_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def run(command, **kwargs):
                if "json" in command:
                    (output / "coverage.json").write_text(
                        json.dumps(
                            {
                                "totals": {
                                    "percent_statements_covered": 100,
                                    "percent_branches_covered": 100,
                                    "missing_branches": 0,
                                }
                            }
                        )
                    )
                return SimpleNamespace(returncode=0 if "json" in command else 1)

            with patch.object(metrics.subprocess, "run", side_effect=run):
                self.assertFalse(metrics.measure("coverage", output)["passed"])

    def test_coverage_reports_branch_and_statement_values_without_inherited_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def run(command, **kwargs):
                self.assertNotIn("COVERAGE_PROCESS_START", kwargs["env"])
                self.assertEqual(
                    str(output.resolve() / ".coverage"), kwargs["env"]["COVERAGE_FILE"]
                )
                if "json" in command:
                    (output / "coverage.json").write_text(
                        json.dumps(
                            {
                                "totals": {
                                    "percent_statements_covered": 90,
                                    "percent_branches_covered": 70,
                                    "percent_covered": 85,
                                    "missing_branches": 3,
                                }
                            }
                        )
                    )
                return SimpleNamespace(returncode=0)

            with (
                patch.dict("os.environ", {"COVERAGE_PROCESS_START": "untrusted.ini"}),
                patch.object(metrics.subprocess, "run", side_effect=run),
            ):
                result = metrics.measure("coverage", output)
            self.assertTrue(result["passed"])
            self.assertEqual(70, result["branch_percent"])
            self.assertEqual(90, result["statement_percent"])

    def test_known_vulnerabilities_remain_a_failure_without_automatic_fixes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def run(command, **kwargs):
                self.assertNotIn("--fix", command)
                self.assertNotIn("--ignore-vuln", command)
                path = Path(command[command.index("--output") + 1])
                vulnerable = path.name == "audit-tool.json"
                path.write_text(
                    json.dumps(
                        {
                            "dependencies": [
                                {
                                    "name": "sdk",
                                    "version": "1",
                                    "vulns": [{"id": "CVE-EXAMPLE"}]
                                    if vulnerable
                                    else [],
                                }
                            ]
                        }
                    )
                )
                return SimpleNamespace(returncode=1 if vulnerable else 0)

            with patch.object(metrics.subprocess, "run", side_effect=run):
                result = metrics.measure("dependencies", output)
            self.assertFalse(result["passed"])
            self.assertEqual(1, result["groups"]["audit-tool"]["vulnerable_packages"])

    def test_separate_audit_groups_continue_after_incomplete_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def run(command, **kwargs):
                path = Path(command[command.index("--output") + 1])
                data = {"dependencies": [{"name": "safe", "version": "1", "vulns": []}]}
                if path.name == "development.json":
                    data = {
                        "dependencies": [
                            {"name": "unknown", "skip_reason": "not audited"}
                        ]
                    }
                path.write_text(json.dumps(data), encoding="utf-8")
                return SimpleNamespace(returncode=0)

            with patch.object(metrics.subprocess, "run", side_effect=run) as child:
                result = metrics.measure("dependencies", output)
            self.assertEqual(2, child.call_count)
            self.assertFalse(result["passed"])
            self.assertFalse(result["groups"]["development"]["passed"])
            self.assertTrue(result["groups"]["audit-tool"]["passed"])

    @patch("scripts.answer_team.answer_team")
    def test_standalone_review_and_research_warn_text_clients_of_partial_review(
        self, run
    ):
        run.return_value = {
            "answer": "Generated answer",
            "model_stages": 3,
            "independent_critique_completed": True,
            "synthesis_required": False,
            "truncation": {"draft": True, "critique": False},
            "artifact_coverage": {"draft_review": {"omitted_chars": 100}},
        }
        for mode in ("review", "research"):
            result = controller.rpc(
                {
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "ask_team",
                        "arguments": {"question": "q", "mode": mode},
                    },
                },
                metrics.ROOT,
            )["result"]
            self.assertIn("Some material was truncated", result["content"][0]["text"])
            self.assertIn("not independently reviewed", result["content"][0]["text"])

    @patch("scripts.answer_team.preflight")
    @patch(
        "scripts.answer_team.run_stage",
        side_effect=["Complete draft", "Complete critique", "Final answer"],
    )
    def test_full_review_does_not_inject_false_partial_coverage_warning(
        self, stage, preflight
    ):
        controller.answer_team("q", mode="review", evidence_scope="supplied")
        self.assertNotIn("unreviewed", stage.call_args_list[-1].args[1])

    def test_invalid_auth_shapes_and_keys_fail_without_exposing_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            for value in (
                [],
                {"google": []},
                {"google": {"type": "api", "key": "private\nvalue"}},
            ):
                path.write_text(json.dumps(value), encoding="utf-8")
                with (
                    self.subTest(value=value),
                    self.assertRaises(access.AccessError) as error,
                ):
                    access.credential("google", path)
                self.assertNotIn("private", str(error.exception))
        with self.assertRaises(RoutingError):
            approved_environment("unknown/model", {})
        self.assertEqual(
            {"keep": "yes"}, approved_environment("openrouter/test", {"keep": "yes"})
        )


if __name__ == "__main__":
    unittest.main()

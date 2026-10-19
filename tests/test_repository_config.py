import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate_repo import (
    ROOT,
    config_errors,
    lint_file,
    repository_files,
    scan_file,
    validate,
)


class RepositoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))

    def test_repository_passes_offline_validation(self):
        self.assertEqual([], validate())

    def test_paid_main_helper_and_specialist_are_rejected(self):
        for field in ("model", "small_model", "specialist"):
            with self.subTest(field=field):
                config = copy.deepcopy(self.config)
                if field == "specialist":
                    config["agent"]["test-designer"]["model"] = (
                        "openrouter/example/paid"
                    )
                else:
                    config[field] = "openrouter/example/paid"
                self.assertTrue(config_errors(config))

    def test_catalog_access_and_price_safety_cannot_be_widened(self):
        changes = [
            lambda c: c.update(enabled_providers=["openrouter", "openai"]),
            lambda c: c["provider"]["openrouter"].pop("whitelist"),
            lambda c: c["provider"]["openrouter"]["whitelist"].append("example/paid"),
        ]
        for change in changes:
            config = copy.deepcopy(self.config)
            change(config)
            self.assertTrue(config_errors(config))
        for key, value in (("allow_fallbacks", True), ("max_price", {"prompt": 1})):
            config = copy.deepcopy(self.config)
            model = next(iter(config["provider"]["openrouter"]["models"].values()))
            model["options"]["provider"][key] = value
            self.assertTrue(config_errors(config))

    def test_shell_side_effects_and_mcp_bypasses_are_rejected(self):
        for role in ("researcher", "test-designer", "junior-developer"):
            for tool in ("bash", "edit", "serena_execute_shell_command", "task"):
                with self.subTest(role=role, tool=tool):
                    config = copy.deepcopy(self.config)
                    config["agent"][role].setdefault("permission", {})[tool] = "allow"
                    self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["agent"]["test-designer"]["permission"] = {
            "bash": {"python -m unittest*": "allow"}
        }
        self.assertTrue(config_errors(config))

    def test_secret_reads_and_unapproved_web_are_rejected(self):
        config = copy.deepcopy(self.config)
        config["permission"]["read"] = "allow"
        self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["agent"]["researcher"]["permission"]["webfetch"] = "allow"
        self.assertTrue(config_errors(config))

    def test_unknown_tools_and_builtin_agents_cannot_bypass_roles(self):
        config = copy.deepcopy(self.config)
        config["permission"]["*"] = "allow"
        self.assertTrue(config_errors(config))

    def test_only_coordinator_can_use_bridge_and_native_delegation_stays_denied(self):
        from scripts.validate_repo import permission_for

        for role in (
            "answer-coordinator",
            "researcher",
            "answer-critic",
            "junior-developer",
            "test-designer",
        ):
            self.assertEqual(
                "allow" if role == "answer-coordinator" else "deny",
                permission_for(self.config, role, "answer_team_ask_team"),
            )
            for target in (
                "researcher",
                "answer-critic",
                "junior-developer",
                "general",
                "arbitrary",
            ):
                self.assertEqual(
                    "deny", permission_for(self.config, role, "task", target)
                )
        config = copy.deepcopy(self.config)
        config["agent"]["answer-coordinator"]["permission"]["task"] = {"*": "allow"}
        self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["agent"]["researcher"]["permission"]["answer_team_ask_team"] = "allow"
        self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["subagent_depth"] = 2
        self.assertTrue(config_errors(config))

    def test_critique_must_use_distinct_model_and_remain_readonly(self):
        config = copy.deepcopy(self.config)
        config["agent"]["answer-critic"]["model"] = config["agent"][
            "answer-coordinator"
        ]["model"]
        self.assertTrue(config_errors(config))
        for role in ("answer-coordinator", "answer-critic"):
            config = copy.deepcopy(self.config)
            config["agent"][role].setdefault("permission", {})["edit"] = "allow"
            self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["agent"]["build"]["disable"] = False
        self.assertTrue(config_errors(config))

    def test_bridge_cannot_be_replaced_with_arbitrary_command_or_short_timeout(self):
        for key, value in (
            ("command", ["unreviewed-server"]),
            ("timeout", 5000),
            ("type", "remote"),
            ("environment", {"OPENCODE_AUTO": "true"}),
        ):
            config = copy.deepcopy(self.config)
            config["mcp"]["answer_team"][key] = value
            self.assertTrue(config_errors(config))

    def test_agent_request_overrides_and_unknown_enabled_mcp_servers_are_rejected(self):
        for key, value in (
            ("options", {"provider": {"allow_fallbacks": True}}),
            ("provider", {"max_price": {"prompt": 1}}),
            ("models", ["paid/fallback"]),
        ):
            config = copy.deepcopy(self.config)
            config["agent"]["researcher"][key] = value
            self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["mcp"]["unreviewed"] = {
            "type": "local",
            "command": ["unreviewed-server"],
        }
        self.assertTrue(config_errors(config))
        config["mcp"]["unreviewed"]["enabled"] = False
        self.assertEqual([], config_errors(config))

    def test_model_alias_and_local_endpoint_overrides_are_rejected(self):
        for field, value in (("id", "example/paid"), ("npm", "example-sdk")):
            config = copy.deepcopy(self.config)
            details = next(iter(config["provider"]["openrouter"]["models"].values()))
            details[field] = value
            self.assertTrue(config_errors(config))
        config = copy.deepcopy(self.config)
        config["provider"]["openrouter"]["options"] = {
            "baseURL": "http://localhost:8000"
        }
        self.assertTrue(config_errors(config))

    def test_gitignore_behavior(self):
        sensitive = [
            ".env",
            ".env.local",
            "nested/.env.production",
            "prod.env",
            "server.key",
            "credentials-prod.json",
            ".aws/credentials",
            ".opencode/auth.json",
            ".codex/auth.json",
            ".serena/project.local.yml",
            ".serena/cache/index",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin", "-z"],
            cwd=ROOT,
            input="\0".join(sensitive).encode() + b"\0",
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            set(sensitive), {os.fsdecode(p) for p in result.stdout.split(b"\0") if p}
        )
        for example in (".env.example", "nested/.env.example", "prod.env.example"):
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "--quiet", example], cwd=ROOT
            )
            self.assertEqual(1, result.returncode, example)


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_tracked_ignored_secret_with_unicode_filename_is_scanned(self):
        subprocess.run(
            ["git", "init", "-q", str(self.root)], check=True, capture_output=True
        )
        (self.root / ".gitignore").write_text("*.env\n", encoding="utf-8")
        filename = "māori credential.env"
        token = "ghp_" + "x" * 40
        (self.root / filename).write_text(token, encoding="utf-8")
        subprocess.run(["git", "add", "-f", "--", filename], cwd=self.root, check=True)
        self.assertIn(filename, repository_files(self.root))
        findings = scan_file(self.root, filename)
        self.assertTrue(any("GitHub token" in item for item in findings))
        self.assertNotIn(token, "\n".join(findings))

    def test_secret_after_one_megabyte_and_across_chunks_is_detected(self):
        token = "sk-or-v1-" + "x" * 40
        (self.root / "large.txt").write_text(
            "a" * (65536 * 17 - 3) + token, encoding="utf-8"
        )
        self.assertTrue(scan_file(self.root, "large.txt"))

    def test_path_outside_checkout_is_rejected(self):
        findings = scan_file(self.root, "../outside.txt")
        self.assertTrue(any("outside checkout" in item for item in findings))

    def test_symlink_is_rejected_without_reading_target(self):
        target = self.root / "target.txt"
        target.write_text("ordinary text", encoding="utf-8")
        try:
            (self.root / "link.txt").symlink_to(target)
        except OSError:
            self.skipTest("Windows symlink privilege is unavailable")
        self.assertTrue(scan_file(self.root, "link.txt"))

    def test_symlink_guard_prevents_reads_on_every_platform(self):
        with (
            patch.object(Path, "is_symlink", return_value=True),
            patch.object(Path, "open") as opened,
        ):
            self.assertTrue(scan_file(self.root, "link.txt"))
            opened.assert_not_called()

    def test_linter_detects_broken_links_and_invalid_python(self):
        (self.root / "page.md").write_text("[missing](missing.md)\n", encoding="utf-8")
        self.assertTrue(lint_file(self.root, "page.md"))
        (self.root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        self.assertTrue(lint_file(self.root, "bad.py"))

    def test_ignored_examples_still_get_content_scanned(self):
        filename = ".env.example"
        (self.root / filename).write_text("ghp_" + "x" * 40, encoding="utf-8")
        self.assertTrue(scan_file(self.root, filename))


if __name__ == "__main__":
    unittest.main()

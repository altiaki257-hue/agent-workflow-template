import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from scripts.check_provider_access import AccessError, NoRedirects, check, credential
from scripts.validate_repo import ROOT, SECRET_PATTERNS, config_errors


class DirectProviderTests(unittest.TestCase):
    def test_new_provider_key_patterns_are_detected(self):
        samples = [b"gsk_" + b"x" * 40, b"AIza" + b"x" * 35]
        for sample in samples:
            self.assertTrue(
                any(pattern.search(sample) for pattern in SECRET_PATTERNS.values())
            )

    def test_only_reviewed_models_and_role_assignments_are_allowed(self):
        original = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
        for provider in ("groq", "google"):
            for field, value in (
                ("options", {"baseURL": "https://untrusted.invalid"}),
                ("npm", "unreviewed-sdk"),
                ("whitelist", ["unreviewed-model"]),
            ):
                config = copy.deepcopy(original)
                config["provider"][provider][field] = value
                self.assertTrue(config_errors(config))
            for field, value in (
                ("cost", {"input": 0, "output": 0}),
                ("id", "paid-alias"),
                ("options", {"apiKey": "not-a-real-key"}),
            ):
                config = copy.deepcopy(original)
                next(iter(config["provider"][provider]["models"].values()))[field] = (
                    value
                )
                self.assertTrue(config_errors(config))
        config = copy.deepcopy(original)
        config["agent"]["researcher"]["model"] = "groq/unreviewed-model"
        self.assertTrue(config_errors(config))
        self.assertFalse(config_errors(original))

    def test_diagnostic_only_gets_fixed_catalog_with_private_header(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"data": [{"id": "openai/gpt-oss-120b"}, {"id": "qwen/qwen3.8-27b"}]}
        ).encode()
        self.assertEqual(2, len(check("groq", "private-test-credential", opener)))
        req = opener.open.call_args.args[0]
        self.assertEqual("GET", req.get_method())
        self.assertEqual("https://api.groq.com/openai/v1/models", req.full_url)
        self.assertNotIn("private-test-credential", req.full_url)
        self.assertIsNone(req.data)

    def test_google_catalog_and_missing_model(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = (
            b'{"models":[{"name":"models/gemini-3.1-flash-lite"}]}'
        )
        self.assertEqual(
            ["gemini-3.1-flash-lite"],
            check("google", "private-test-credential", opener),
        )
        response.read.return_value = b'{"models":[]}'
        with self.assertRaises(AccessError):
            check("google", "private-test-credential", opener)

    def test_upstream_errors_do_not_leak_or_retry(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(
            "https://example.invalid/private",
            429,
            "private-test-credential",
            {},
            io.BytesIO(b"private upstream detail"),
        )
        with self.assertRaises(AccessError) as error:
            check("groq", "private-test-credential", opener)
        self.assertNotIn("private", str(error.exception))
        self.assertIn("429", str(error.exception))
        opener.open.assert_called_once()
        with self.assertRaises(AccessError):
            NoRedirects().redirect_request(
                None, None, 302, "", {}, "https://untrusted.invalid"
            )

    def test_bad_credential_store_never_exposes_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text("private malformed content", encoding="utf-8")
            with self.assertRaises(AccessError) as error:
                credential("google", path)
            self.assertNotIn("private malformed content", str(error.exception))
            path.write_text(
                '{"google":{"type":"api","key":"stored-test-key"}}', encoding="utf-8"
            )
            with patch.dict("os.environ", {"GEMINI_API_KEY": "environment-test-key"}):
                self.assertEqual("stored-test-key", credential("google", path))


if __name__ == "__main__":
    unittest.main()

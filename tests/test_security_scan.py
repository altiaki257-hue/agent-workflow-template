"""Scanner integrity failures cannot execute a download or replace owner files."""

import hashlib
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import security_scan as scanner


class Download(io.BytesIO):
    url = "https://release-assets.githubusercontent.com/scanner"


class SecurityScannerTests(unittest.TestCase):
    def test_unsupported_platform_fails_without_download(self):
        with (
            patch.object(scanner.platform, "system", return_value="Unknown"),
            patch.object(scanner.urllib.request, "urlopen") as fetch,
            self.assertRaises(ValueError),
        ):
            scanner.install(Path(tempfile.gettempdir()) / "unused-scanner")
        fetch.assert_not_called()

    def test_bad_download_is_not_published_or_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(scanner, "selected_asset", return_value=("tool", "0" * 64)),
                patch.object(scanner.urllib.request, "urlopen", return_value=Download(b"bad")),
                patch.object(scanner.subprocess, "run") as execute,
                self.assertRaises(ValueError),
            ):
                scanner.install(root)
            self.assertEqual([], list(root.iterdir()))
            execute.assert_not_called()

    def test_successful_install_and_owner_file_preservation(self):
        content = b"verified fixture"
        digest = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(scanner, "selected_asset", return_value=("tool", digest)),
                patch.object(scanner.urllib.request, "urlopen", return_value=Download(content)) as fetch,
            ):
                path = scanner.install(root)
                self.assertEqual(content, path.read_bytes())
                self.assertEqual(path, scanner.install(root))
                self.assertEqual(1, fetch.call_count)
                path.write_bytes(b"owner file")
                with self.assertRaises(ValueError):
                    scanner.install(root)
                self.assertEqual(b"owner file", path.read_bytes())
                with patch.object(scanner.subprocess, "run") as execute:
                    with self.assertRaises(ValueError):
                        scanner.scan("scan", root)
                execute.assert_not_called()
        with self.assertRaises(ValueError):
            scanner.install(scanner.ROOT / "scanner")

    def test_local_rules_keep_strict_errors_and_disable_updates(self):
        with (
            patch.object(scanner, "verified_binary", return_value=Path("verified-tool")),
            patch.object(scanner.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as execute,
        ):
            self.assertEqual(1, scanner.scan("scan", Path("unused")))
            command = execute.call_args.args[0]
            self.assertIn("--strict", command)
            self.assertIn("--disable-version-check", command)
            self.assertEqual(["--error", "scripts"], command[-2:])
            self.assertEqual(".semgrep/agent-security.yml", command[command.index("--config") + 1])
            scanner.scan("controls", Path("unused"))
            self.assertEqual(["--test", ".semgrep/agent-security.py"], execute.call_args.args[0][-2:])


if __name__ == "__main__":
    unittest.main()

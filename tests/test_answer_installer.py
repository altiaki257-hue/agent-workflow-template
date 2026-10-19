import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AnswerInstallerTests(unittest.TestCase):
    def test_opt_in_preserves_other_servers_and_existing_environment(self):
        source = (ROOT / "scripts/install_answer_team.ps1").read_text(encoding="utf-8")
        code = re.search(r"@'\n(import re\n.*?)\n'@", source, re.S).group(1)
        for style in ("absent", "inline", "table"):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script, config = root / "configure.py", root / "config.toml"
                text = '[mcp_servers.answer_team]\ncommand = "python"\nargs = ["owned.py"]\n'
                if style == "inline":
                    text += (
                        'env = { KEEP = "synthetic-value", ANSWER_TEAM_LANGFUSE = "0", '
                        + 'TEMP = '
                        + json.dumps(r"C:\tmp\synthetic")
                        + ' }\n'
                    )
                if style == "table":
                    text += '[mcp_servers.answer_team.env]\nKEEP = "synthetic-value"\nANSWER_TEAM_LANGFUSE = "0"\n'
                text += '[mcp_servers.unrelated]\ncommand = "other"\n[mcp_servers.unrelated.env]\nKEEP = "synthetic-secret"\n'
                before = tomllib.loads(text)["mcp_servers"]["unrelated"]
                config.write_text(text, encoding="utf-8")
                script.write_text(code, encoding="utf-8")
                for _ in range(2):
                    result = subprocess.run(
                        [sys.executable, str(script), str(config), "1"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    configured = tomllib.loads(config.read_text(encoding="utf-8"))[
                        "mcp_servers"
                    ]
                    self.assertEqual(before, configured["unrelated"])
                    self.assertEqual(
                        "1", configured["answer_team"]["env"]["ANSWER_TEAM_LANGFUSE"]
                    )
                    self.assertEqual(300, configured["answer_team"]["tool_timeout_sec"])
                    if style != "absent":
                        self.assertEqual(
                            "synthetic-value", configured["answer_team"]["env"]["KEEP"]
                        )
                    if style == "inline":
                        self.assertEqual(
                            r"C:\tmp\synthetic",
                            configured["answer_team"]["env"]["TEMP"],
                        )


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.check_quality import run_check


class QualityRunnerTests(unittest.TestCase):
    def test_failure_is_visible_and_complete_output_remains_available(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            contextlib.redirect_stdout(io.StringIO()) as summary,
        ):
            passed = run_check(
                "failure",
                [sys.executable, "-c", "print('failure detail'); raise SystemExit(3)"],
                Path(directory),
            )
            result = json.loads(summary.getvalue())
            self.assertFalse(passed)
            self.assertFalse(result["passed"])
            self.assertNotIn("failure detail", summary.getvalue())
            self.assertIn(
                "failure detail", Path(result["full_log"]).read_text(encoding="utf-8")
            )

    def test_success_is_compact_and_removes_its_log(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            contextlib.redirect_stdout(io.StringIO()) as summary,
        ):
            passed = run_check(
                "success",
                [sys.executable, "-c", "print('detail\\n' * 1000)"],
                Path(directory),
            )
            self.assertTrue(passed)
            self.assertTrue(json.loads(summary.getvalue())["passed"])
            self.assertLess(len(summary.getvalue()), 200)
            self.assertEqual([], list(Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()

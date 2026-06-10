from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest

from powerbi_mcp.cli import doctor_main


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"


class CLITests(unittest.TestCase):
    def test_doctor_accepts_fixture_project_without_full_validation(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = doctor_main(["--project", str(FIXTURE_PROJECT_PATH), "--no-validate"])

        self.assertEqual(exit_code, 0)
        text = output.getvalue()
        self.assertIn("[OK] python:", text)
        self.assertIn("[OK] dependency:mcp:", text)
        self.assertIn("[OK] pbip:", text)
        self.assertIn("[OK] report_dir:", text)
        self.assertIn("[OK] model_dir:", text)

    def test_doctor_returns_nonzero_for_missing_project(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = doctor_main(["--project", str(FIXTURE_PROJECT_PATH / "missing")])

        self.assertEqual(exit_code, 1)
        self.assertIn("[FAIL] project:", output.getvalue())


if __name__ == "__main__":
    unittest.main()

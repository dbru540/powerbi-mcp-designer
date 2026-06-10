import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from powerbi_mcp.validation.report import ValidationReport, ValidationIssue

FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
FIRST_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"
FIRST_VISUAL_ID = "080c3bdfee4f864670b1"


class PostValidationRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.project = Path(self.tmp) / "example"
        shutil.copytree(str(FIXTURE_PROJECT_PATH), str(self.project))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _visual_path(self) -> Path:
        return (
            self.project
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "visuals"
            / FIRST_VISUAL_ID
            / "visual.json"
        )

    def test_post_write_failure_restores_file_from_backup(self) -> None:
        from powerbi_mcp.report.write import report_update_visual_title

        visual = self._visual_path()
        original_content = visual.read_text(encoding="utf-8")

        bad_report = ValidationReport(
            ok=False,
            issues=[
                ValidationIssue(
                    "error",
                    "TEST_E001",
                    "Injected post-validation failure",
                    str(visual),
                    None,
                )
            ],
        )

        with patch("powerbi_mcp.report.write.post_validate_paths", return_value=bad_report):
            result = report_update_visual_title(
                project_path=str(self.project),
                page_id=FIRST_PAGE_ID,
                visual_id=FIRST_VISUAL_ID,
                title="New Title",
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "post-validation failed")
        self.assertIn("validation", result)
        self.assertFalse(result["validation"]["ok"])
        # File must be restored to original content
        self.assertEqual(visual.read_text(encoding="utf-8"), original_content)

    def test_pre_write_failure_aborts_without_disk_changes(self) -> None:
        from powerbi_mcp.report.write import report_update_visual_title

        visual = self._visual_path()
        original_content = visual.read_text(encoding="utf-8")

        bad_report = ValidationReport(
            ok=False,
            issues=[
                ValidationIssue(
                    "error",
                    "TEST_E001",
                    "Injected pre-validation failure",
                    str(visual),
                    None,
                )
            ],
        )

        with patch("powerbi_mcp.report.write.pre_validate_payload", return_value=bad_report):
            result = report_update_visual_title(
                project_path=str(self.project),
                page_id=FIRST_PAGE_ID,
                visual_id=FIRST_VISUAL_ID,
                title="New Title",
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "pre-validation failed")
        self.assertIn("validation", result)
        self.assertFalse(result["validation"]["ok"])
        # File must be unchanged — no write occurred
        self.assertEqual(visual.read_text(encoding="utf-8"), original_content)
        # No .bak files should exist
        bak_files = list(self.project.rglob("*.bak"))
        self.assertEqual(bak_files, [])


if __name__ == "__main__":
    unittest.main()

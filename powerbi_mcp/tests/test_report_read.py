from pathlib import Path
import json
import shutil
import tempfile
import unittest

from powerbi_mcp.report.read import (
    project_get_summary,
    report_get_summary,
    report_list_pages,
    report_list_visuals,
)


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
FIRST_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"
FIRST_VISUAL_ID = "080c3bdfee4f864670b1"


class ReportReadTests(unittest.TestCase):
    def test_project_get_summary_contains_report_and_model_fixture_metadata(self) -> None:
        summary = project_get_summary(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(summary["page_count"], 13)
        self.assertEqual(summary["visual_count"], 141)
        self.assertEqual(summary["table_count"], 11)
        self.assertEqual(summary["model_name"], "Model")
        self.assertTrue(Path(summary["report_dir"]).name.endswith(".Report"))

    def test_report_get_summary_counts_fixture_pages_and_visuals(self) -> None:
        summary = report_get_summary(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(summary["page_count"], 13)
        self.assertEqual(summary["visual_count"], 141)
        self.assertTrue(Path(summary["report_dir"]).name.endswith(".Report"))

    def test_report_list_pages_returns_fixture_page_metadata(self) -> None:
        result = report_list_pages(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(result["count"], 13)
        first_page = result["pages"][0]
        self.assertEqual(first_page["id"], FIRST_PAGE_ID)
        self.assertEqual(first_page["displayName"], "Time & material")
        self.assertEqual(first_page["width"], 1280)
        self.assertEqual(first_page["height"], 720)
        self.assertEqual(first_page["visual_count"], 17)

    def test_report_list_visuals_returns_fixture_visual_metadata(self) -> None:
        result = report_list_visuals(str(FIXTURE_PROJECT_PATH), FIRST_PAGE_ID)

        self.assertEqual(result["count"], 17)
        visuals_by_id = {visual["id"]: visual for visual in result["visuals"]}
        self.assertIn(FIRST_VISUAL_ID, visuals_by_id)
        self.assertEqual(visuals_by_id[FIRST_VISUAL_ID]["visualType"], "slicer")
        self.assertEqual(visuals_by_id[FIRST_VISUAL_ID]["title"], "Display mode")
        self.assertEqual(visuals_by_id[FIRST_VISUAL_ID]["position"]["width"], 90)

    def test_report_list_pages_ignores_hidden_visual_directories(self) -> None:
        tmp_dir = tempfile.mkdtemp()
        try:
            project_dir = Path(tmp_dir) / "demo"
            page_dir = project_dir / "Demo.Report" / "definition" / "pages" / "p1"
            active_visual = page_dir / "visuals" / "v1"
            backup_dir = page_dir / "visuals" / ".backups" / "old" / "v0"
            active_visual.mkdir(parents=True)
            backup_dir.mkdir(parents=True)

            (project_dir / "Demo.pbip").write_text("{}", encoding="utf-8")
            (page_dir.parent / "pages.json").write_text(json.dumps({"pageOrder": ["p1"]}), encoding="utf-8")
            (page_dir / "page.json").write_text(json.dumps({"displayName": "Demo"}), encoding="utf-8")
            (active_visual / "visual.json").write_text(json.dumps({"visual": {"visualType": "card"}}), encoding="utf-8")
            (backup_dir / "visual.json").write_text(json.dumps({"visual": {"visualType": "card"}}), encoding="utf-8")

            result = report_list_pages(str(project_dir))

            self.assertEqual(result["pages"][0]["visual_count"], 1)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

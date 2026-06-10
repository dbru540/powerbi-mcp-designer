import json
import unittest
from pathlib import Path

from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.visual_ai.desktop_evidence import (
    report_design_desktop_evidence_summary,
    summarize_desktop_evidence,
)


TEMP_ROOT = named_temp_root("visual_ai_desktop_evidence")


class DesktopEvidenceSummaryTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TEMP_ROOT.exists():
            for child in TEMP_ROOT.iterdir():
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    import shutil

                    shutil.rmtree(child, ignore_errors=True)
            try:
                TEMP_ROOT.rmdir()
            except OSError:
                pass

    def test_summarizes_ready_and_low_content_page_evidence(self) -> None:
        qa_result = {
            "desktop": {"capture_screenshot_requested": True, "capture_all_pages_requested": True},
            "projects": [
                {
                    "name": "Survey",
                    "desktop_launch": {
                        "attempted": True,
                        "page_screenshots": [
                            {
                                "page_index": 0,
                                "page_id": "p1",
                                "page_name": "Overview",
                                "screenshot": {"path": "C:/qa/overview.bmp"},
                                "render_readiness": {"status": "ready", "content_ratio": 0.31},
                                "render_retry": {"status": "ready", "attempt_count": 2},
                            },
                            {
                                "page_index": 1,
                                "page_id": "p2",
                                "page_name": "Detail",
                                "screenshot": {"path": "C:/qa/detail.bmp"},
                                "render_readiness": {"status": "low-content", "content_ratio": 0.004},
                                "render_retry": {"status": "timeout", "attempt_count": 3},
                            },
                        ],
                    },
                }
            ],
        }

        summary = summarize_desktop_evidence(qa_result)

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["totals"]["pages"], 2)
        self.assertEqual(summary["totals"]["ready"], 1)
        self.assertEqual(summary["totals"]["low_content"], 1)
        self.assertEqual(summary["usable_page_count"], 1)
        self.assertEqual(summary["unusable_page_count"], 1)
        self.assertEqual(summary["pages"][1]["evidence_status"], "low-content")
        self.assertIn("Do not use", summary["pages"][1]["recommendation"])

    def test_reads_summary_from_visual_qa_report_file(self) -> None:
        report_file = TEMP_ROOT / "visual-qa-report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(
            json.dumps(
                {
                    "desktop": {"capture_screenshot_requested": True},
                    "projects": [
                        {
                            "name": "Survey",
                            "desktop_launch": {
                                "attempted": True,
                                "screenshot": {"path": "C:/qa/report.bmp"},
                                "render_readiness": {"status": "ready", "content_ratio": 0.2},
                                "render_retry": {"status": "not-needed", "attempt_count": 1},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        summary = report_design_desktop_evidence_summary(str(report_file))

        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["report_file"], str(report_file.resolve(strict=False)))
        self.assertEqual(summary["totals"]["ready"], 1)
        self.assertEqual(summary["pages"][0]["project_name"], "Survey")

    def test_missing_report_file_returns_blocked_summary(self) -> None:
        summary = report_design_desktop_evidence_summary(str(TEMP_ROOT / "missing.json"))

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("not found", summary["error"])


if __name__ == "__main__":
    unittest.main()

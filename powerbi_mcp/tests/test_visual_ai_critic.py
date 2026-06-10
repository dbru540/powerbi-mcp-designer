import unittest
import json
from pathlib import Path

from powerbi_mcp.visual_ai.critic import page_design_audit, report_design_audit, visual_design_audit
from powerbi_mcp.tests._temp_roots import named_temp_root


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TIME_MATERIAL_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"
CARD_VISUAL_ID = "31481fc86904ea242477"
TEMP_ROOT = named_temp_root("visual_ai_critic")


class VisualAICriticTests(unittest.TestCase):
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

    def test_page_design_audit_returns_score_and_findings(self) -> None:
        result = page_design_audit(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="monitor project margin status",
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertIn(result["grade"], {"excellent", "strong", "needs-improvement", "weak"})
        self.assertGreater(result["visual_count"], 0)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 5)
        self.assertTrue(any(finding["dimension"] == "density" for finding in result["findings"]))

    def test_visual_design_audit_flags_missing_title_for_bound_visual(self) -> None:
        result = visual_design_audit(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            CARD_VISUAL_ID,
            audience="executive",
            intent="monitor status",
        )

        self.assertEqual(result["visual_id"], CARD_VISUAL_ID)
        self.assertEqual(result["visual_type"], "card")
        self.assertGreaterEqual(result["binding_count"], 1)
        self.assertTrue(any(finding["dimension"] == "title clarity" for finding in result["findings"]))

    def test_report_design_audit_aggregates_pages(self) -> None:
        result = report_design_audit(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="monitor consulting performance",
        )

        self.assertEqual(result["page_count"], 13)
        self.assertGreater(result["visual_count"], 100)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 5)
        self.assertGreaterEqual(len(result["page_audits"]), 1)

    def test_report_design_audit_adds_nonblocking_gate_for_low_content_desktop_evidence(self) -> None:
        report_file = TEMP_ROOT / "visual-qa-report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(
            json.dumps(
                {
                    "desktop": {"capture_screenshot_requested": True},
                    "projects": [
                        {
                            "name": "Focus",
                            "desktop_launch": {
                                "attempted": True,
                                "page_screenshots": [
                                    {
                                        "page_index": 0,
                                        "page_id": TIME_MATERIAL_PAGE_ID,
                                        "page_name": "Time & material",
                                        "screenshot": {"path": "C:/qa/time.bmp"},
                                        "render_readiness": {"status": "low-content", "content_ratio": 0.004},
                                        "render_retry": {"status": "timeout", "attempt_count": 3},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = report_design_audit(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="monitor consulting performance",
            visual_qa_report_file=str(report_file),
        )

        self.assertFalse(result["visual_evidence_gate"]["screenshot_based_critique_allowed"])
        self.assertEqual(result["visual_evidence_gate"]["desktop_evidence_status"], "needs-render")
        self.assertEqual(result["visual_evidence_gate"]["ready_pages"], 0)
        self.assertTrue(any(finding["dimension"] == "visual evidence quality" for finding in result["evidence_findings"]))
        self.assertFalse(any(finding["dimension"] == "visual evidence quality" for finding in result["findings"]))

    def test_report_design_audit_allows_screenshot_critique_for_ready_desktop_evidence(self) -> None:
        report_file = TEMP_ROOT / "ready-visual-qa-report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(
            json.dumps(
                {
                    "desktop": {"capture_screenshot_requested": True},
                    "projects": [
                        {
                            "name": "Focus",
                            "desktop_launch": {
                                "attempted": True,
                                "screenshot": {"path": "C:/qa/focus.bmp"},
                                "render_readiness": {"status": "ready", "content_ratio": 0.2},
                                "render_retry": {"status": "not-needed", "attempt_count": 1},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = report_design_audit(
            str(FIXTURE_PROJECT_PATH),
            visual_qa_report_file=str(report_file),
        )

        self.assertTrue(result["visual_evidence_gate"]["screenshot_based_critique_allowed"])
        self.assertEqual(result["visual_evidence_gate"]["desktop_evidence_status"], "ready")
        self.assertEqual(result["evidence_findings"], [])

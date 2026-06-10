import json
import unittest
from pathlib import Path

from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.visual_ai.studio import report_design_studio_plan


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("visual_ai_studio")


class VisualAIStudioTests(unittest.TestCase):
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

    def test_report_design_studio_plan_orchestrates_critic_layout_and_actions(self) -> None:
        result = report_design_studio_plan(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="overview of consulting margin performance",
            page_limit=1,
        )

        self.assertEqual(result["audience"], "executive")
        self.assertFalse(result["mutates_files"])
        self.assertIn(result["maturity"], {"weak", "needs-improvement", "strong", "excellent"})
        self.assertEqual(len(result["page_studies"]), 1)
        study = result["page_studies"][0]
        self.assertIn("layout_recommendation", study)
        self.assertIn("title_actions", study)
        self.assertIn("layout_snap_actions", study)
        self.assertIn("reflow_actions", study)
        self.assertGreaterEqual(result["action_summary"]["total_actions"], 1)
        self.assertEqual(result["execution_sequence"][0]["step"], "audit")
        self.assertEqual(result["execution_sequence"][-1]["dry_run_default"], True)

    def test_studio_plan_uses_file_first_only_when_desktop_evidence_needs_render(self) -> None:
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
                                "screenshot": {"path": "C:/qa/focus.bmp"},
                                "render_readiness": {"status": "low-content", "content_ratio": 0.004},
                                "render_retry": {"status": "timeout", "attempt_count": 3},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = report_design_studio_plan(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="overview of consulting margin performance",
            page_limit=1,
            visual_qa_report_file=str(report_file),
        )

        self.assertEqual(result["critique_mode"], "file-first-only")
        self.assertFalse(result["visual_evidence_gate"]["screenshot_based_critique_allowed"])
        self.assertGreaterEqual(len(result["evidence_findings"]), 1)
        self.assertIn("Desktop evidence is not ready", result["critique_guidance"])

    def test_studio_plan_allows_screenshot_informed_mode_for_ready_desktop_evidence(self) -> None:
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
                                "render_readiness": {"status": "ready", "content_ratio": 0.25},
                                "render_retry": {"status": "not-needed", "attempt_count": 1},
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = report_design_studio_plan(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="overview of consulting margin performance",
            page_limit=1,
            visual_qa_report_file=str(report_file),
        )

        self.assertEqual(result["critique_mode"], "screenshot-informed")
        self.assertTrue(result["visual_evidence_gate"]["screenshot_based_critique_allowed"])
        self.assertEqual(result["evidence_findings"], [])


if __name__ == "__main__":
    unittest.main()

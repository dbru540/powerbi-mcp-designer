import unittest
from pathlib import Path

from powerbi_mcp.visual_ai.improvements import page_design_improve_plan, report_design_improve_plan


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TIME_MATERIAL_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"


class VisualAIImprovementsTests(unittest.TestCase):
    def test_page_design_improve_plan_prioritizes_quick_wins(self) -> None:
        result = page_design_improve_plan(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="monitor project margin status",
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertIn("quick_wins", result)
        self.assertIn("structural_recommendations", result)
        self.assertGreater(len(result["quick_wins"]) + len(result["structural_recommendations"]), 0)
        self.assertFalse(result["mutates_files"])

    def test_report_design_improve_plan_aggregates_page_plans(self) -> None:
        result = report_design_improve_plan(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="monitor consulting performance",
        )

        self.assertEqual(result["page_count"], 13)
        self.assertGreaterEqual(len(result["page_plans"]), 1)
        self.assertIn("manual_review", result)
        self.assertFalse(result["mutates_files"])

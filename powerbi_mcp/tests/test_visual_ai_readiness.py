import unittest
from pathlib import Path

from powerbi_mcp.visual_ai.readiness import report_design_readiness_check


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"


class VisualAIReadinessTests(unittest.TestCase):
    def test_report_design_readiness_check_reports_mvp_and_remaining_gates(self) -> None:
        result = report_design_readiness_check(
            str(FIXTURE_PROJECT_PATH),
            audience="executive",
            intent="overview of consulting margin performance",
            page_limit=1,
        )

        self.assertEqual(result["project_path"], str(FIXTURE_PROJECT_PATH))
        self.assertFalse(result["mutates_files"])
        self.assertEqual(result["status"], "mvp-ready")
        self.assertTrue(result["validation"]["ok"])
        self.assertGreaterEqual(result["readiness_score"], 0.7)
        self.assertTrue(any(item["capability"] == "report_design_studio_plan" for item in result["capabilities"]))
        self.assertTrue(any(gate["gate"] == "visual_qa" for gate in result["remaining_gates"]))
        self.assertIn("report_design_studio_plan", result["recommended_entrypoint"])


if __name__ == "__main__":
    unittest.main()

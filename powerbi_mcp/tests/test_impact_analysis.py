from pathlib import Path
import unittest

from powerbi_mcp.analysis.impact import find_unused_measures, impact_of_model_reference


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"


class ImpactAnalysisTests(unittest.TestCase):
    def test_find_unused_measures_returns_known_unused_measure(self) -> None:
        result = find_unused_measures(str(FIXTURE_PROJECT_PATH))

        self.assertGreater(result["count"], 0)
        unused_names = {(measure["table"], measure["name"]) for measure in result["unused_measures"]}
        self.assertIn(("Budget", "Budget"), unused_names)
        self.assertNotIn(("Budgeted tickets", "Fixed price - Margin"), unused_names)

    def test_impact_of_model_reference_returns_affected_pages_and_visuals(self) -> None:
        result = impact_of_model_reference(
            str(FIXTURE_PROJECT_PATH),
            "Budgeted tickets",
            "Fixed price - Margin",
        )

        self.assertEqual(result["entity"], "Budgeted tickets")
        self.assertEqual(result["property_name"], "Fixed price - Margin")
        self.assertEqual(result["affected_page_count"], 1)
        self.assertEqual(result["affected_visual_count"], 3)
        self.assertEqual(result["affected_pages"], ["Marge Mensuelle"])
        self.assertEqual(
            {visual["title"] for visual in result["affected_visuals"]},
            {
                "Margin Contribution by Team Member",
                "Margin by Project Manager",
                "Monthly Margin Trend",
            },
        )

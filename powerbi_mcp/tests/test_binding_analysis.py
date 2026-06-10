from pathlib import Path
import unittest

from powerbi_mcp.analysis.bindings import (
    find_report_objects_by_model_reference,
    report_get_visual_bindings,
)


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
MARGIN_PAGE_ID = "fafca104d30f4cd6912f"
MARGIN_VISUAL_ID = "b17e2b972f8f404aa82f"


class BindingAnalysisTests(unittest.TestCase):
    def test_report_get_visual_bindings_returns_query_state_projections(self) -> None:
        result = report_get_visual_bindings(
            str(FIXTURE_PROJECT_PATH),
            MARGIN_PAGE_ID,
            MARGIN_VISUAL_ID,
        )

        self.assertEqual(result["page_id"], MARGIN_PAGE_ID)
        self.assertEqual(result["page_name"], "Marge Mensuelle")
        self.assertEqual(result["visual_id"], MARGIN_VISUAL_ID)
        self.assertEqual(result["visual_type"], "lineChart")
        self.assertEqual(result["title"], "Monthly Margin Trend")
        self.assertEqual(result["count"], 2)
        self.assertTrue(Path(result["path"]).name == "visual.json")

        bindings_by_role = {binding["role"]: binding for binding in result["bindings"]}

        self.assertEqual(bindings_by_role["Category"]["field_type"], "Column")
        self.assertEqual(bindings_by_role["Category"]["entity"], "Calendar Month")
        self.assertEqual(bindings_by_role["Category"]["property"], "MonthText")
        self.assertEqual(
            bindings_by_role["Category"]["query_ref"],
            "Calendar Month.MonthText",
        )
        self.assertEqual(bindings_by_role["Category"]["native_query_ref"], "Month")
        self.assertTrue(bindings_by_role["Category"]["active"])

        self.assertEqual(bindings_by_role["Y"]["field_type"], "Measure")
        self.assertEqual(bindings_by_role["Y"]["entity"], "Budgeted tickets")
        self.assertEqual(bindings_by_role["Y"]["property"], "Fixed price - Margin")
        self.assertEqual(bindings_by_role["Y"]["query_ref"], "Budgeted tickets.Margin")
        self.assertEqual(bindings_by_role["Y"]["native_query_ref"], "Margin")
        self.assertTrue(bindings_by_role["Y"]["active"])

    def test_find_report_objects_by_model_reference_returns_matching_visuals(self) -> None:
        result = find_report_objects_by_model_reference(
            str(FIXTURE_PROJECT_PATH),
            "Budgeted tickets",
            "Fixed price - Margin",
        )

        self.assertEqual(result["entity"], "Budgeted tickets")
        self.assertEqual(result["property_name"], "Fixed price - Margin")
        self.assertEqual(result["count"], 3)

        matches_by_id = {match["visual_id"]: match for match in result["matches"]}
        self.assertEqual(
            set(matches_by_id),
            {
                "1abd08352de747579972",
                "a22430adcefd460e9e7c",
                "b17e2b972f8f404aa82f",
            },
        )

        self.assertEqual(
            {match["title"] for match in result["matches"]},
            {
                "Margin Contribution by Team Member",
                "Margin by Project Manager",
                "Monthly Margin Trend",
            },
        )

        for match in result["matches"]:
            self.assertEqual(match["page_id"], MARGIN_PAGE_ID)
            self.assertEqual(match["page_name"], "Marge Mensuelle")
            self.assertTrue(Path(match["path"]).name == "visual.json")
            self.assertEqual(len(match["matching_bindings"]), 1)
            self.assertEqual(match["matching_bindings"][0]["role"], "Y")
            self.assertEqual(match["matching_bindings"][0]["field_type"], "Measure")
            self.assertEqual(
                match["matching_bindings"][0]["entity"],
                "Budgeted tickets",
            )
            self.assertEqual(
                match["matching_bindings"][0]["property"],
                "Fixed price - Margin",
            )


if __name__ == "__main__":
    unittest.main()

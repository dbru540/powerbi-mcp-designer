import unittest
from pathlib import Path

from powerbi_mcp.visual_ai.design_expert import report_design_brief_generate
from powerbi_mcp.visual_ai.planner import visual_plan_generate


class VisualAIPlannerTests(unittest.TestCase):
    def test_visual_plan_generate_prefers_line_chart_for_monthly_trend(self) -> None:
        result = visual_plan_generate(
            intent="show monthly margin trend by manager",
            dimensions=[
                {"kind": "dimension", "entity": "Calendar Month", "property": "MonthText"},
                {"kind": "dimension", "entity": "Projects", "property": "Project manager"},
            ],
            measures=[
                {"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"},
            ],
            audience="executive",
        )

        self.assertEqual(result["recommended_visual_type"], "lineChart")
        self.assertEqual(result["generation_path"], "native-pbir")
        self.assertEqual(result["suggested_assignments"]["Category"][0]["property"], "MonthText")
        self.assertEqual(result["suggested_assignments"]["Y"][0]["property"], "Fixed price - Margin")
        self.assertTrue(result["requirements"]["ok"])

    def test_visual_plan_generate_uses_card_for_single_measure_kpi(self) -> None:
        result = visual_plan_generate(
            intent="show current margin KPI",
            dimensions=[],
            measures=[
                {"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"},
            ],
            audience="executive",
        )

        self.assertEqual(result["recommended_visual_type"], "card")
        self.assertIn("Values", result["suggested_assignments"])
        self.assertTrue(result["requirements"]["ok"])

    def test_visual_plan_generate_supports_focus_native_visual_families(self) -> None:
        dimensions = [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}]
        time_dimensions = [{"kind": "dimension", "entity": "Calendar", "property": "YearMonth"}]
        measures = [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}]

        cases = [
            ("show horizontal bar ranking by project", dimensions, measures, "barChart"),
            ("show vertical column comparison by project", dimensions, measures, "columnChart"),
            ("show donut share by project", dimensions, measures, "donutChart"),
            ("show pie share by project", dimensions, measures, "pieChart"),
            ("show pivot matrix by project and month", dimensions + time_dimensions, measures, "pivotTable"),
            ("add a background shape panel", [], [], "shape"),
            ("add a logo image placeholder", [], [], "image"),
        ]
        for intent, dims, mets, expected in cases:
            with self.subTest(expected=expected):
                result = visual_plan_generate(intent=intent, dimensions=dims, measures=mets)

                self.assertEqual(result["recommended_visual_type"], expected)
                self.assertEqual(result["generation_path"], "native-pbir")
                self.assertTrue(result["requirements"]["ok"])

    def test_report_design_brief_generate_returns_executive_overview_recipe(self) -> None:
        result = report_design_brief_generate(
            audience="executive",
            intent="overview of consulting margin performance",
            subject="margin",
        )

        self.assertEqual(result["page_archetype"], "executive-overview")
        self.assertEqual(result["sections"][0]["zone"], "hero")
        self.assertIn("card", result["sections"][0]["recommended_visuals"])
        self.assertIn("lineChart", result["sections"][1]["recommended_visuals"])

    def test_visual_plan_generate_can_attach_local_template_reference(self) -> None:
        fixture_project_path = Path(__file__).resolve().parents[2] / "example"

        result = visual_plan_generate(
            intent="show monthly margin trend",
            dimensions=[
                {"kind": "dimension", "entity": "Calendar Month", "property": "MonthText"},
            ],
            measures=[
                {"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"},
            ],
            template_project_path=str(fixture_project_path),
        )

        self.assertEqual(result["recommended_visual_type"], "lineChart")
        self.assertTrue(result["template_reference"]["found"])
        self.assertEqual(result["template_reference"]["template"]["visual_type"], "lineChart")

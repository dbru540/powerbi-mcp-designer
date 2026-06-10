import unittest

from powerbi_mcp.visual_ai.catalog import visual_catalog_list, visual_requirements_check


class VisualAICatalogTests(unittest.TestCase):
    def test_visual_catalog_list_returns_first_native_visual_families(self) -> None:
        result = visual_catalog_list()

        self.assertEqual(result["count"], 14)
        visual_ids = {visual["id"] for visual in result["visuals"]}
        self.assertEqual(
            visual_ids,
            {
                "barChart",
                "card",
                "columnChart",
                "lineChart",
                "clusteredBarChart",
                "clusteredColumnChart",
                "donutChart",
                "image",
                "pieChart",
                "pivotTable",
                "shape",
                "tableEx",
                "slicer",
                "textbox",
            },
        )

    def test_visual_requirements_check_flags_missing_measure_role(self) -> None:
        result = visual_requirements_check(
            "lineChart",
            assignments={
                "Category": [{"kind": "dimension", "entity": "Calendar", "property": "Month"}],
            },
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_roles"], ["Y"])

    def test_visual_requirements_check_accepts_valid_card_assignment(self) -> None:
        result = visual_requirements_check(
            "card",
            assignments={
                "Values": [{"kind": "measure", "entity": "Budget", "property": "Actual"}],
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["missing_roles"], [])
        self.assertEqual(result["invalid_roles"], [])

    def test_visual_requirements_check_accepts_pivot_roles(self) -> None:
        result = visual_requirements_check(
            "pivotTable",
            assignments={
                "Rows": [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                "Columns": [{"kind": "dimension", "entity": "Calendar", "property": "YearMonth"}],
                "Values": [{"kind": "measure", "entity": "Budget", "property": "Actual"}],
            },
        )

        self.assertTrue(result["ok"])

    def test_visual_requirements_check_accepts_presentation_visuals_without_roles(self) -> None:
        for visual_type in ("shape", "image", "textbox"):
            with self.subTest(visual_type=visual_type):
                result = visual_requirements_check(visual_type, assignments={})

                self.assertTrue(result["ok"])

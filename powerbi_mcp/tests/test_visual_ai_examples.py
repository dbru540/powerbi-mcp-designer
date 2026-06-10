from pathlib import Path
import unittest

from powerbi_mcp.visual_ai.examples import (
    custom_visual_eligibility,
    visual_examples_list,
    visual_role_examples,
    visual_template_library,
    visual_template_recommend,
)


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
EXTERNAL_FOCUS_PROJECT_PATHS = [
    Path("C:/Users/DavidBru/FIVEFORTY/Documents/_WORK/540/Interne/PBI"),
    Path("/mnt/c/Users/DavidBru/FIVEFORTY/Documents/_WORK/540/Interne/PBI"),
]


def _focus_project_path() -> Path:
    for candidate in EXTERNAL_FOCUS_PROJECT_PATHS:
        if candidate.exists():
            return candidate
    return FIXTURE_PROJECT_PATH


class VisualAIExamplesTests(unittest.TestCase):
    def test_visual_examples_list_mines_real_pbir_visuals_by_type(self) -> None:
        result = visual_examples_list(str(FIXTURE_PROJECT_PATH), visual_type="lineChart")

        self.assertEqual(result["visual_type"], "lineChart")
        self.assertGreaterEqual(result["total_matches"], 2)
        self.assertGreaterEqual(result["returned_count"], 1)
        first = result["examples"][0]
        self.assertEqual(first["visual_type"], "lineChart")
        self.assertIn("page_id", first)
        self.assertIn("visual_id", first)
        self.assertIn("Category", first["query_roles"])
        self.assertIn("Y", first["query_roles"])
        self.assertIn("layout", first)
        self.assertGreater(first["layout"]["width"], 0)

    def test_visual_examples_list_can_limit_examples_per_type(self) -> None:
        result = visual_examples_list(
            str(FIXTURE_PROJECT_PATH),
            supported_only=True,
            max_examples_per_type=1,
        )

        self.assertGreaterEqual(result["type_count"], 3)
        type_counts: dict[str, int] = {}
        for example in result["examples"]:
            type_counts[example["visual_type"]] = type_counts.get(example["visual_type"], 0) + 1

        self.assertTrue(type_counts)
        self.assertTrue(all(count == 1 for count in type_counts.values()))
        self.assertIn("shape", type_counts)
        self.assertIn("image", type_counts)

    def test_visual_template_recommend_prefers_examples_with_bindings(self) -> None:
        result = visual_template_recommend(str(FIXTURE_PROJECT_PATH), "clusteredBarChart")

        self.assertEqual(result["visual_type"], "clusteredBarChart")
        self.assertTrue(result["found"])
        template = result["template"]
        self.assertEqual(template["visual_type"], "clusteredBarChart")
        self.assertIn("Category", template["query_roles"])
        self.assertIn("Y", template["query_roles"])
        self.assertGreaterEqual(template["template_score"], 2)

    def test_visual_template_recommend_reports_missing_type(self) -> None:
        result = visual_template_recommend(str(FIXTURE_PROJECT_PATH), "waterfallChart")

        self.assertEqual(result["visual_type"], "waterfallChart")
        self.assertFalse(result["found"])
        self.assertEqual(result["template"], None)

    def test_visual_template_library_groups_best_templates_roles_and_style_defaults(self) -> None:
        project_path = _focus_project_path()

        result = visual_template_library(str(project_path), supported_only=True)

        self.assertGreaterEqual(result["visual_count"], 100)
        self.assertIn("lineChart", result["templates_by_type"])
        self.assertIn("pivotTable", result["templates_by_type"])
        self.assertIn("slicer", result["templates_by_type"])
        self.assertIn("Category", result["role_examples"]["lineChart"])
        self.assertIn("Y", result["role_examples"]["lineChart"])
        self.assertIn("Rows", result["role_examples"]["pivotTable"])
        self.assertIn("Columns", result["role_examples"]["pivotTable"])
        self.assertIn("Values", result["role_examples"]["pivotTable"])
        line_style = result["style_defaults"]["lineChart"]
        self.assertIn("categoryAxis", line_style["objects"])
        self.assertIn("valueAxis", line_style["objects"])
        self.assertIn("visualHeader", line_style["visualContainerObjects"])

    def test_visual_role_examples_counts_real_power_bi_roles(self) -> None:
        project_path = _focus_project_path()

        result = visual_role_examples(str(project_path), visual_type="pivotTable")

        self.assertEqual(result["visual_type"], "pivotTable")
        self.assertGreaterEqual(result["roles"]["Rows"]["projection_count"], 1)
        self.assertGreaterEqual(result["roles"]["Columns"]["projection_count"], 1)
        self.assertGreaterEqual(result["roles"]["Values"]["projection_count"], 1)
        self.assertTrue(result["roles"]["Rows"]["sample_bindings"])

    def test_custom_visual_eligibility_detects_focus_custom_visuals(self) -> None:
        project_path = _focus_project_path()
        if project_path == FIXTURE_PROJECT_PATH:
            self.skipTest("External Focus PBIP project is not available")

        result = custom_visual_eligibility(str(project_path))

        names = {visual["name"]: visual for visual in result["custom_visuals"]}
        self.assertIn("CalendarVisual", names)
        self.assertIn("WordCloud", names)
        self.assertIn("textFilter", names)
        self.assertFalse(names["CalendarVisual"]["can_generate_native_pbir"])
        self.assertEqual(names["textFilter"]["recommended_native_fallback"], "slicer")

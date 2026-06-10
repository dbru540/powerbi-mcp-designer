import json
import shutil
import unittest
import uuid
from pathlib import Path

from powerbi_mcp.report.read import report_list_visuals
from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.visual_ai.compiler import visual_plan_apply, visual_plan_generate_and_apply
from powerbi_mcp.visual_ai.planner import visual_plan_generate


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("visual_ai_compiler")
FIRST_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"


class VisualAICompilerTests(unittest.TestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_visual_plan_apply_creates_native_line_chart_from_plan(self) -> None:
        project_dir = self.make_fixture_copy()
        plan = visual_plan_generate(
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

        before = report_list_visuals(str(project_dir), FIRST_PAGE_ID)
        result = visual_plan_apply(
            str(project_dir),
            FIRST_PAGE_ID,
            plan,
            x=40,
            y=60,
            dry_run=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["visual_type"], "lineChart")
        self.assertFalse(result["dry_run"])
        after = report_list_visuals(str(project_dir), FIRST_PAGE_ID)
        self.assertEqual(after["count"], before["count"] + 1)
        new_visual_id = result["applied_result"]["visual_id"]
        visual_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "visuals"
            / new_visual_id
            / "visual.json"
        )
        visual_data = json.loads(visual_path.read_text(encoding="utf-8"))
        self.assertEqual(visual_data["visual"]["visualType"], "lineChart")
        self.assertEqual(visual_data["position"]["x"], 40)
        self.assertEqual(visual_data["position"]["y"], 60)
        self.assertIn("Category", visual_data["visual"]["query"]["queryState"])
        self.assertIn("Y", visual_data["visual"]["query"]["queryState"])

    def test_visual_plan_apply_creates_focus_visual_families_from_plans(self) -> None:
        project_dir = self.make_fixture_copy()
        cases = [
            (
                "show horizontal bar ranking by project",
                [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "barChart",
                {"Category", "Y"},
            ),
            (
                "show vertical column comparison by project",
                [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "columnChart",
                {"Category", "Y"},
            ),
            (
                "show donut share by project",
                [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "donutChart",
                {"Category", "Y"},
            ),
            (
                "show pie share by project",
                [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "pieChart",
                {"Category", "Y"},
            ),
            (
                "show pivot matrix by project and month",
                [
                    {"kind": "dimension", "entity": "Projects", "property": "Project Name"},
                    {"kind": "dimension", "entity": "Calendar", "property": "YearMonth"},
                ],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "pivotTable",
                {"Rows", "Columns", "Values"},
            ),
            (
                "show operational detail table",
                [{"kind": "dimension", "entity": "Projects", "property": "Project Name"}],
                [{"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"}],
                "tableEx",
                {"Values"},
            ),
        ]

        for index, (intent, dimensions, measures, visual_type, roles) in enumerate(cases):
            with self.subTest(visual_type=visual_type):
                plan = visual_plan_generate(intent=intent, dimensions=dimensions, measures=measures)
                result = visual_plan_apply(
                    str(project_dir),
                    FIRST_PAGE_ID,
                    plan,
                    x=20,
                    y=20 + index * 10,
                    dry_run=False,
                )

                self.assertTrue(result["success"])
                self.assertEqual(result["visual_type"], visual_type)
                visual_path = (
                    project_dir
                    / "Focus.Report"
                    / "definition"
                    / "pages"
                    / FIRST_PAGE_ID
                    / "visuals"
                    / result["applied_result"]["visual_id"]
                    / "visual.json"
                )
                visual_data = json.loads(visual_path.read_text(encoding="utf-8"))
                self.assertEqual(visual_data["visual"]["visualType"], visual_type)
                self.assertEqual(set(visual_data["visual"]["query"]["queryState"].keys()), roles)

    def test_visual_plan_apply_creates_presentation_visuals_without_query(self) -> None:
        project_dir = self.make_fixture_copy()
        for visual_type, intent in (
            ("shape", "add a background shape panel"),
            ("image", "add a logo image placeholder"),
            ("textbox", "add a narrative header"),
        ):
            with self.subTest(visual_type=visual_type):
                plan = visual_plan_generate(intent=intent)
                result = visual_plan_apply(
                    str(project_dir),
                    FIRST_PAGE_ID,
                    plan,
                    dry_run=False,
                )

                self.assertTrue(result["success"])
                self.assertEqual(result["visual_type"], visual_type)
                visual_path = (
                    project_dir
                    / "Focus.Report"
                    / "definition"
                    / "pages"
                    / FIRST_PAGE_ID
                    / "visuals"
                    / result["applied_result"]["visual_id"]
                    / "visual.json"
                )
                visual_data = json.loads(visual_path.read_text(encoding="utf-8"))
                self.assertEqual(visual_data["visual"]["visualType"], visual_type)
                self.assertNotIn("query", visual_data["visual"])

    def test_visual_plan_apply_defaults_to_dry_run_and_leaves_fixture_unchanged(self) -> None:
        project_dir = self.make_fixture_copy()
        plan = visual_plan_generate(
            intent="show current margin KPI",
            measures=[
                {"kind": "measure", "entity": "Budgeted tickets", "property": "Fixed price - Margin"},
            ],
            audience="executive",
        )

        before = report_list_visuals(str(project_dir), FIRST_PAGE_ID)
        result = visual_plan_apply(
            str(project_dir),
            FIRST_PAGE_ID,
            plan,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        after = report_list_visuals(str(project_dir), FIRST_PAGE_ID)
        self.assertEqual(after["count"], before["count"])

    def test_visual_plan_generate_and_apply_rejects_deneb_path(self) -> None:
        project_dir = self.make_fixture_copy()

        result = visual_plan_generate_and_apply(
            str(project_dir),
            FIRST_PAGE_ID,
            intent="show advanced bespoke chart",
            preferred_path="deneb",
        )

        self.assertIn("error", result)

import json
from pathlib import Path
import shutil
import unittest
import uuid

from powerbi_mcp.report.write import (
    report_create_page,
    report_create_visual,
    report_move_visual,
    report_rename_page,
    report_update_page_size,
    report_update_visual_title,
)
from powerbi_mcp.tests._temp_roots import named_temp_root


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("report_write")
FIRST_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"
FIRST_VISUAL_ID = "080c3bdfee4f864670b1"


class ReportWriteTests(unittest.TestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_report_create_page_persists_page_and_pages_json_with_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        pages_dir = project_dir / "Focus.Report" / "definition" / "pages"
        pages_json_path = pages_dir / "pages.json"
        original_meta = json.loads(pages_json_path.read_text(encoding="utf-8"))

        result = report_create_page(str(project_dir), "Task 4 Test Page")

        self.assertTrue(result["success"])
        self.assertEqual(result["displayName"], "Task 4 Test Page")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        new_page_id = result["page_id"]
        page_dir = pages_dir / new_page_id
        self.assertTrue(page_dir.is_dir())
        self.assertTrue((page_dir / "visuals").is_dir())

        page_data = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
        self.assertEqual(page_data["name"], new_page_id)
        self.assertEqual(page_data["displayName"], "Task 4 Test Page")

        updated_meta = json.loads(pages_json_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_meta["pageOrder"][:-1], original_meta["pageOrder"])
        self.assertEqual(updated_meta["pageOrder"][-1], new_page_id)

        backups_dir = pages_json_path.parent / ".backups"
        backup_files = sorted(backups_dir.glob("pages.json.*.bak"))
        self.assertTrue(backup_files, "expected a backup for pages.json")

    def test_report_create_page_dry_run_reports_changes_without_mutating_files(self) -> None:
        project_dir = self.make_fixture_copy()
        pages_dir = project_dir / "Focus.Report" / "definition" / "pages"
        pages_json_path = pages_dir / "pages.json"
        original_meta_text = pages_json_path.read_text(encoding="utf-8")
        original_page_dirs = {path.name for path in pages_dir.iterdir() if path.is_dir()}

        result = report_create_page(str(project_dir), "Dry Run Page", dry_run=True)

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(pages_json_path.read_text(encoding="utf-8"), original_meta_text)
        self.assertEqual(
            {path.name for path in pages_dir.iterdir() if path.is_dir()},
            original_page_dirs,
        )
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

    def test_report_create_slicer_defaults_to_power_bi_dropdown_mode(self) -> None:
        project_dir = self.make_fixture_copy()

        result = report_create_visual(
            str(project_dir),
            FIRST_PAGE_ID,
            "slicer",
            x=10,
            y=20,
            width=180,
            height=58,
            title="Time",
            category_entity="TimeType",
            category_property="Time",
        )

        self.assertTrue(result["success"])
        visual_json_path = Path(result["path"]) / "visual.json"
        visual_data = json.loads(visual_json_path.read_text(encoding="utf-8"))
        mode = visual_data["visual"]["objects"]["data"][0]["properties"]["mode"]
        self.assertEqual(mode["expr"]["Literal"]["Value"], "'Dropdown'")
        self.assertIn("header", visual_data["visual"]["objects"])
        self.assertIn("selection", visual_data["visual"]["objects"])
        self.assertIn("visualHeader", visual_data["visual"]["visualContainerObjects"])

    def test_report_create_chart_keeps_desktop_style_defaults_when_title_is_set(self) -> None:
        project_dir = self.make_fixture_copy()

        result = report_create_visual(
            str(project_dir),
            FIRST_PAGE_ID,
            "lineChart",
            x=10,
            y=90,
            width=420,
            height=260,
            title="Trend",
            category_entity="Calendar",
            category_property="YearMonth",
            measure_entity="Actual",
            measure_property="Actual Amount",
        )

        self.assertTrue(result["success"])
        visual_json_path = Path(result["path"]) / "visual.json"
        visual_data = json.loads(visual_json_path.read_text(encoding="utf-8"))
        visual = visual_data["visual"]
        self.assertIn("labels", visual["objects"])
        self.assertIn("categoryAxis", visual["objects"])
        self.assertIn("valueAxis", visual["objects"])
        self.assertIn("title", visual["visualContainerObjects"])
        self.assertIn("visualHeader", visual["visualContainerObjects"])
        self.assertIn("visualTooltip", visual["visualContainerObjects"])

    def test_report_create_table_and_pivot_use_focus_derived_grid_defaults(self) -> None:
        project_dir = self.make_fixture_copy()

        for visual_type in ("tableEx", "pivotTable"):
            with self.subTest(visual_type=visual_type):
                result = report_create_visual(
                    str(project_dir),
                    FIRST_PAGE_ID,
                    visual_type,
                    x=10,
                    y=90,
                    width=520,
                    height=280,
                    title=visual_type,
                    category_entity="Calendar",
                    category_property="YearMonth",
                    measure_entity="Actual",
                    measure_property="Actual Amount",
                )

                self.assertTrue(result["success"])
                visual_json_path = Path(result["path"]) / "visual.json"
                visual_data = json.loads(visual_json_path.read_text(encoding="utf-8"))
                objects = visual_data["visual"]["objects"]
                self.assertIn("grid", objects)
                self.assertIn("columnHeaders", objects)
                self.assertIn("values", objects)

    def test_report_move_visual_updates_position_and_writes_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        visual_json_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "visuals"
            / FIRST_VISUAL_ID
            / "visual.json"
        )
        original_visual = json.loads(visual_json_path.read_text(encoding="utf-8"))

        result = report_move_visual(
            str(project_dir),
            FIRST_PAGE_ID,
            FIRST_VISUAL_ID,
            x=321,
            y=654,
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_visual = json.loads(visual_json_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_visual["position"]["x"], 321)
        self.assertEqual(updated_visual["position"]["y"], 654)
        self.assertEqual(updated_visual["position"]["width"], original_visual["position"]["width"])
        self.assertEqual(updated_visual["position"]["height"], original_visual["position"]["height"])

        backups_dir = visual_json_path.parent / ".backups"
        backup_files = sorted(backups_dir.glob("visual.json.*.bak"))
        self.assertTrue(backup_files, "expected a backup for visual.json")

    def test_report_move_visual_dry_run_leaves_visual_json_unchanged(self) -> None:
        project_dir = self.make_fixture_copy()
        visual_json_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "visuals"
            / FIRST_VISUAL_ID
            / "visual.json"
        )
        original_visual_text = visual_json_path.read_text(encoding="utf-8")

        result = report_move_visual(
            str(project_dir),
            FIRST_PAGE_ID,
            FIRST_VISUAL_ID,
            x=111,
            y=222,
            dry_run=True,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(visual_json_path.read_text(encoding="utf-8"), original_visual_text)
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

    def test_report_update_visual_title_persists_new_title_and_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        visual_json_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "visuals"
            / FIRST_VISUAL_ID
            / "visual.json"
        )

        result = report_update_visual_title(
            str(project_dir),
            FIRST_PAGE_ID,
            FIRST_VISUAL_ID,
            "Task 10 Title",
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_visual = json.loads(visual_json_path.read_text(encoding="utf-8"))
        title_value = (
            updated_visual["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]
        )
        self.assertEqual(title_value, "'Task 10 Title'")

        backup_files = sorted((visual_json_path.parent / ".backups").glob("visual.json.*.bak"))
        self.assertTrue(backup_files, "expected a backup for visual.json")

    def test_report_update_page_size_persists_dimensions(self) -> None:
        project_dir = self.make_fixture_copy()
        page_json_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "page.json"
        )

        result = report_update_page_size(
            str(project_dir),
            FIRST_PAGE_ID,
            width=1440,
            height=900,
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_page = json.loads(page_json_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_page["width"], 1440)
        self.assertEqual(updated_page["height"], 900)

    def test_report_rename_page_persists_display_name(self) -> None:
        project_dir = self.make_fixture_copy()
        page_json_path = (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / FIRST_PAGE_ID
            / "page.json"
        )

        result = report_rename_page(
            str(project_dir),
            FIRST_PAGE_ID,
            "Task 10 Page Name",
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_page = json.loads(page_json_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_page["displayName"], "Task 10 Page Name")


if __name__ == "__main__":
    unittest.main()

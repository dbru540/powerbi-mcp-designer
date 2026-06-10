import json
import shutil
import unittest
import uuid
from pathlib import Path

from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.visual_ai.workbench import (
    page_design_action_plan,
    page_design_apply_quick_wins,
    page_layout_action_plan,
    page_layout_apply_quick_wins,
    page_layout_apply_reflow_plan,
    report_layout_apply_quick_wins,
    report_design_apply_quick_wins,
)


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("visual_ai_workbench")
TIME_MATERIAL_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"
UNTITLED_BOUND_VISUAL_ID = "169342452639d12cb001"


class VisualAIWorkbenchTests(unittest.TestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def visual_path(self, project_dir: Path, visual_id: str = UNTITLED_BOUND_VISUAL_ID) -> Path:
        return (
            project_dir
            / "Focus.Report"
            / "definition"
            / "pages"
            / TIME_MATERIAL_PAGE_ID
            / "visuals"
            / visual_id
            / "visual.json"
        )

    def test_page_design_action_plan_suggests_titles_for_bound_untitled_visuals(self) -> None:
        result = page_design_action_plan(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="monitor project performance",
            max_actions=3,
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertFalse(result["mutates_files"])
        title_actions = [
            action
            for action in result["actions"]
            if action["action_type"] == "set_visual_title"
        ]
        self.assertTrue(title_actions)
        self.assertEqual(title_actions[0]["visual_id"], UNTITLED_BOUND_VISUAL_ID)
        self.assertIsNone(title_actions[0]["current_title"])
        self.assertIn("Project Name", title_actions[0]["proposed_title"])

    def test_page_design_apply_quick_wins_defaults_to_dry_run(self) -> None:
        project_dir = self.make_fixture_copy()
        visual_path = self.visual_path(project_dir)
        original_text = visual_path.read_text(encoding="utf-8")

        result = page_design_apply_quick_wins(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="monitor project performance",
            max_actions=1,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["attempted_count"], 1)
        self.assertEqual(visual_path.read_text(encoding="utf-8"), original_text)

    def test_page_design_apply_quick_wins_can_write_title(self) -> None:
        project_dir = self.make_fixture_copy()
        result = page_design_apply_quick_wins(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="monitor project performance",
            max_actions=1,
            dry_run=False,
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["applied_count"], 1)
        action = result["results"][0]["action"]
        visual_data = json.loads(self.visual_path(project_dir, action["visual_id"]).read_text(encoding="utf-8"))
        title_value = (
            visual_data["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"]
        )
        self.assertEqual(title_value, f"'{action['proposed_title']}'")

    def test_report_design_apply_quick_wins_limits_scope(self) -> None:
        project_dir = self.make_fixture_copy()
        result = report_design_apply_quick_wins(
            str(project_dir),
            audience="executive",
            intent="monitor consulting performance",
            page_limit=1,
            max_actions_per_page=1,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["attempted_count"], 1)
        self.assertEqual(len(result["page_results"]), 1)

    def test_page_layout_action_plan_suggests_grid_snap_for_data_visuals(self) -> None:
        result = page_layout_action_plan(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            grid_size=8,
            max_actions=2,
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertFalse(result["mutates_files"])
        self.assertGreaterEqual(result["action_count"], 1)
        action = result["actions"][0]
        self.assertEqual(action["action_type"], "snap_visual_to_grid")
        self.assertEqual(action["visual_id"], "080c3bdfee4f864670b1")
        self.assertEqual(action["proposed_position"]["x"] % 8, 0)
        self.assertEqual(action["proposed_position"]["y"] % 8, 0)
        self.assertIn("current_position", action)

    def test_page_layout_apply_quick_wins_defaults_to_dry_run(self) -> None:
        project_dir = self.make_fixture_copy()
        visual_path = self.visual_path(project_dir, "080c3bdfee4f864670b1")
        original_text = visual_path.read_text(encoding="utf-8")

        result = page_layout_apply_quick_wins(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            grid_size=8,
            max_actions=1,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["attempted_count"], 1)
        self.assertEqual(visual_path.read_text(encoding="utf-8"), original_text)

    def test_page_layout_apply_quick_wins_can_write_position(self) -> None:
        project_dir = self.make_fixture_copy()
        result = page_layout_apply_quick_wins(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            grid_size=8,
            max_actions=1,
            dry_run=False,
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["applied_count"], 1)
        action = result["results"][0]["action"]
        visual_data = json.loads(self.visual_path(project_dir, action["visual_id"]).read_text(encoding="utf-8"))
        self.assertEqual(visual_data["position"]["x"], action["proposed_position"]["x"])
        self.assertEqual(visual_data["position"]["y"], action["proposed_position"]["y"])

    def test_report_layout_apply_quick_wins_limits_scope(self) -> None:
        project_dir = self.make_fixture_copy()
        result = report_layout_apply_quick_wins(
            str(project_dir),
            page_limit=1,
            grid_size=8,
            max_actions_per_page=1,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["attempted_count"], 1)

    def test_page_layout_apply_reflow_plan_defaults_to_dry_run(self) -> None:
        project_dir = self.make_fixture_copy()
        card_visual_id = "31481fc86904ea242477"
        visual_path = self.visual_path(project_dir, card_visual_id)
        original_text = visual_path.read_text(encoding="utf-8")

        result = page_layout_apply_reflow_plan(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="overview of consulting margin performance",
            max_moves=1,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["attempted_count"], 1)
        self.assertEqual(visual_path.read_text(encoding="utf-8"), original_text)

    def test_page_layout_apply_reflow_plan_can_write_position(self) -> None:
        project_dir = self.make_fixture_copy()
        result = page_layout_apply_reflow_plan(
            str(project_dir),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="overview of consulting margin performance",
            max_moves=1,
            dry_run=False,
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["applied_count"], 1)
        action = result["results"][0]["action"]
        visual_data = json.loads(self.visual_path(project_dir, action["visual_id"]).read_text(encoding="utf-8"))
        self.assertEqual(visual_data["position"]["x"], action["proposed_position"]["x"])
        self.assertEqual(visual_data["position"]["width"], action["proposed_position"]["width"])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from powerbi_mcp.visual_ai.layout import (
    page_layout_analyze,
    page_layout_blueprint_generate,
    page_layout_recommend,
    page_layout_reflow_plan,
)


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TIME_MATERIAL_PAGE_ID = "ReportSectiona73ab10ffb0f4759f223"


class VisualAILayoutTests(unittest.TestCase):
    def test_page_layout_analyze_detects_zones_and_overlaps(self) -> None:
        result = page_layout_analyze(str(FIXTURE_PROJECT_PATH), TIME_MATERIAL_PAGE_ID)

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertEqual(result["page_size"], {"width": 1280, "height": 720})
        self.assertGreater(result["visual_count"], 0)
        self.assertGreater(result["overlap_count"], 0)
        self.assertIn("left_rail", result["zone_summary"])
        self.assertIn("main_stage", result["zone_summary"])
        self.assertTrue(result["focal_candidates"])
        self.assertLessEqual(
            result["focal_candidates"][0]["area"],
            result["page_size"]["width"] * result["page_size"]["height"],
        )

    def test_page_layout_blueprint_generate_returns_executive_zones(self) -> None:
        result = page_layout_blueprint_generate(
            audience="executive",
            intent="overview of consulting margin performance",
        )

        self.assertEqual(result["page_archetype"], "executive-overview")
        zones_by_name = {zone["zone"]: zone for zone in result["zones"]}
        self.assertIn("hero", zones_by_name)
        self.assertIn("trend", zones_by_name)
        self.assertIn("breakdown", zones_by_name)
        self.assertEqual(zones_by_name["hero"]["priority"], 1)
        self.assertIn("card", zones_by_name["hero"]["recommended_visuals"])

    def test_page_layout_recommend_compares_current_page_to_blueprint(self) -> None:
        result = page_layout_recommend(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="overview of consulting margin performance",
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertEqual(result["blueprint"]["page_archetype"], "executive-overview")
        self.assertGreater(result["recommendation_count"], 0)
        self.assertTrue(any(item["type"] == "overlap_review" for item in result["recommendations"]))
        self.assertFalse(result["mutates_files"])

    def test_page_layout_reflow_plan_maps_existing_visuals_to_blueprint_zones(self) -> None:
        result = page_layout_reflow_plan(
            str(FIXTURE_PROJECT_PATH),
            TIME_MATERIAL_PAGE_ID,
            audience="executive",
            intent="overview of consulting margin performance",
            max_moves=3,
        )

        self.assertEqual(result["page_id"], TIME_MATERIAL_PAGE_ID)
        self.assertFalse(result["mutates_files"])
        self.assertGreaterEqual(result["action_count"], 1)
        hero_action = next(action for action in result["actions"] if action["target_zone"] == "hero")
        self.assertEqual(hero_action["action_type"], "move_visual_to_zone")
        self.assertEqual(hero_action["visual_type"], "card")
        self.assertEqual(hero_action["proposed_position"]["x"], 32)
        self.assertEqual(hero_action["proposed_position"]["width"], 1216)


if __name__ == "__main__":
    unittest.main()

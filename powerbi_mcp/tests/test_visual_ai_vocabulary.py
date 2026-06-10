import unittest

from powerbi_mcp.visual_ai.vocabulary import visual_vocabulary_classify


class VisualAIVocabularyTests(unittest.TestCase):
    def test_classifies_trend_intent(self) -> None:
        result = visual_vocabulary_classify(
            "show monthly margin trend by project manager",
            audience="executive",
        )

        self.assertEqual(result["primary_intent"], "trend")
        self.assertIn("trend", result["intents"])
        self.assertEqual(result["audience"], "executive")
        self.assertGreaterEqual(result["confidence"], 0.7)
        self.assertIn("lineChart", result["recommended_visual_families"])

    def test_classifies_operational_monitoring_intent(self) -> None:
        result = visual_vocabulary_classify(
            "monitor daily SLA exceptions and overdue tickets",
            audience="operations",
        )

        self.assertEqual(result["primary_intent"], "monitor status")
        self.assertIn("inspect detail", result["intents"])
        self.assertIn("card", result["recommended_visual_families"])
        self.assertIn("tableEx", result["recommended_visual_families"])

    def test_classifies_ranking_intent(self) -> None:
        result = visual_vocabulary_classify(
            "rank the top customers by revenue",
            audience="analyst",
        )

        self.assertEqual(result["primary_intent"], "rank")
        self.assertIn("clusteredBarChart", result["recommended_visual_families"])
        self.assertIn("tableEx", result["recommended_visual_families"])

    def test_falls_back_to_inspect_detail_for_unclear_intent(self) -> None:
        result = visual_vocabulary_classify("look at the project data")

        self.assertEqual(result["primary_intent"], "inspect detail")
        self.assertLess(result["confidence"], 0.7)

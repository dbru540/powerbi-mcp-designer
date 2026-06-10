import unittest

from powerbi_mcp.visual_ai.rubric import (
    build_finding,
    grade_for_score,
    summarize_scores,
)


class VisualAIRubricTests(unittest.TestCase):
    def test_grade_for_score_uses_expected_bands(self) -> None:
        self.assertEqual(grade_for_score(4.7), "excellent")
        self.assertEqual(grade_for_score(4.0), "strong")
        self.assertEqual(grade_for_score(3.2), "needs-improvement")
        self.assertEqual(grade_for_score(2.0), "weak")

    def test_build_finding_returns_stable_shape(self) -> None:
        finding = build_finding(
            dimension="visual hierarchy",
            severity="warning",
            score=2.0,
            evidence="Page has 17 visuals.",
            recommendation="Reduce competing focal points.",
            page_id="PageA",
            visual_id="VisualB",
        )

        self.assertEqual(finding["dimension"], "visual hierarchy")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["page_id"], "PageA")
        self.assertEqual(finding["visual_id"], "VisualB")
        self.assertEqual(finding["score"], 2.0)

    def test_summarize_scores_averages_dimensions_and_grades_result(self) -> None:
        summary = summarize_scores(
            [
                build_finding("layout balance", "info", 4.0, "Balanced.", "Keep structure."),
                build_finding("density", "warning", 2.0, "Too dense.", "Reduce visual count."),
            ]
        )

        self.assertEqual(summary["score"], 3.0)
        self.assertEqual(summary["grade"], "needs-improvement")
        self.assertEqual(summary["finding_count"], 2)

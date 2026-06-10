import unittest

from powerbi_mcp.visual_ai.windows_capture import title_is_powerbi_candidate, win32_input_size


class VisualAIWindowsCaptureTests(unittest.TestCase):
    def test_powerbi_project_title_without_powerbi_text_is_candidate_when_preferred(self) -> None:
        self.assertTrue(
            title_is_powerbi_candidate(
                "questionnaires-satisfaction",
                ["questionnaires-satisfaction"],
            )
        )

    def test_unrelated_window_title_is_not_candidate(self) -> None:
        self.assertFalse(title_is_powerbi_candidate("Downloads", ["questionnaires-satisfaction"]))

    def test_send_input_uses_native_win32_input_size(self) -> None:
        self.assertIn(win32_input_size(), {28, 40})


if __name__ == "__main__":
    unittest.main()

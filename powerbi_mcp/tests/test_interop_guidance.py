import unittest

from powerbi_mcp.interop import get_powerbi_modeling_mcp_interop_guidance


class InteropGuidanceTests(unittest.TestCase):
    def test_interop_guidance_describes_complementary_split(self) -> None:
        guidance = get_powerbi_modeling_mcp_interop_guidance()

        self.assertEqual(guidance["interop_status"], "complementary")
        self.assertIn(
            "PBIP/PBIR file-first report and UI metadata operations",
            guidance["recommended_split"]["this_repo"],
        )
        self.assertIn(
            "Live semantic-model operations against Power BI Desktop",
            guidance["recommended_split"]["microsoft_powerbi_modeling_mcp"],
        )
        self.assertIn(
            "Desktop/Fabric connection handling",
            guidance["do_not_duplicate"],
        )

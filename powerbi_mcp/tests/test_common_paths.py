import shutil
from pathlib import Path
import unittest
import uuid

import mcp
import powerbi_mcp.server as powerbi_server

from powerbi_mcp.common.paths import (
    ProjectPaths,
    find_model_dir,
    find_pbip_file,
    find_report_dir,
    get_project_summary_paths,
)
from powerbi_mcp.tests._temp_roots import named_temp_root


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("common_paths")


class CommonPathsTests(unittest.TestCase):
    def make_temp_project_dir(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        project_dir.mkdir()
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_local_package_preserves_upstream_mcp_api(self) -> None:
        self.assertTrue(hasattr(mcp, "ClientSession"))
        self.assertTrue(hasattr(mcp, "ServerSession"))

    def test_find_pbip_file_returns_fixture_pbip(self) -> None:
        self.assertEqual(
            find_pbip_file(FIXTURE_PROJECT_PATH),
            FIXTURE_PROJECT_PATH / "Focus.pbip",
        )

    def test_find_report_dir_returns_fixture_report_dir(self) -> None:
        self.assertEqual(
            find_report_dir(FIXTURE_PROJECT_PATH),
            FIXTURE_PROJECT_PATH / "Focus.Report",
        )

    def test_find_model_dir_returns_fixture_model_dir(self) -> None:
        self.assertEqual(
            find_model_dir(FIXTURE_PROJECT_PATH),
            FIXTURE_PROJECT_PATH / "Focus.SemanticModel",
        )

    def test_get_project_summary_paths_returns_expected_summary(self) -> None:
        summary = get_project_summary_paths(FIXTURE_PROJECT_PATH)

        self.assertIsInstance(summary, ProjectPaths)
        self.assertEqual(summary.project_dir, FIXTURE_PROJECT_PATH)
        self.assertEqual(summary.pbip_file, FIXTURE_PROJECT_PATH / "Focus.pbip")
        self.assertEqual(summary.report_dir, FIXTURE_PROJECT_PATH / "Focus.Report")
        self.assertEqual(summary.model_dir, FIXTURE_PROJECT_PATH / "Focus.SemanticModel")
        self.assertEqual(
            summary.pages_dir,
            FIXTURE_PROJECT_PATH / "Focus.Report" / "definition" / "pages",
        )
        self.assertEqual(
            summary.tables_dir,
            FIXTURE_PROJECT_PATH / "Focus.SemanticModel" / "definition" / "tables",
        )

    def test_get_project_summary_paths_keeps_report_dir_when_pages_child_is_missing(self) -> None:
        project_dir = self.make_temp_project_dir()
        report_dir = project_dir / "Scratch.Report"
        (report_dir / "definition").mkdir(parents=True)

        summary = get_project_summary_paths(project_dir)

        self.assertEqual(summary.report_dir, report_dir)
        self.assertEqual(summary.pages_dir, report_dir / "definition" / "pages")
        self.assertFalse(summary.pages_dir.exists())

    def test_get_project_summary_paths_keeps_model_dir_when_tables_child_is_missing(self) -> None:
        project_dir = self.make_temp_project_dir()
        model_dir = project_dir / "Scratch.SemanticModel"
        (model_dir / "definition").mkdir(parents=True)

        summary = get_project_summary_paths(project_dir)

        self.assertEqual(summary.model_dir, model_dir)
        self.assertEqual(summary.tables_dir, model_dir / "definition" / "tables")
        self.assertFalse(summary.tables_dir.exists())

    def test_report_list_pages_reports_missing_pages_directory_when_report_exists(self) -> None:
        project_dir = self.make_temp_project_dir()
        (project_dir / "Scratch.Report" / "definition").mkdir(parents=True)

        self.assertEqual(
            powerbi_server.report_list_pages(str(project_dir)),
            {"error": f"Pages directory not found in {project_dir}"},
        )

    def test_list_tables_reports_missing_tables_directory_when_model_exists(self) -> None:
        project_dir = self.make_temp_project_dir()
        (project_dir / "Scratch.SemanticModel" / "definition").mkdir(parents=True)

        self.assertEqual(
            powerbi_server.list_tables(str(project_dir)),
            {"error": "Tables directory not found"},
        )

    def test_get_table_content_reports_missing_tables_directory_when_model_exists(self) -> None:
        project_dir = self.make_temp_project_dir()
        (project_dir / "Scratch.SemanticModel" / "definition").mkdir(parents=True)

        self.assertEqual(
            powerbi_server.get_table_content(str(project_dir), "AnyTable"),
            {"error": "Tables directory not found"},
        )

    def test_legacy_get_project_info_wrapper_returns_report_and_model_counts(self) -> None:
        result = powerbi_server.get_project_info(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(result["page_count"], 13)
        self.assertEqual(result["visual_count"], 141)
        self.assertEqual(result["table_count"], 11)
        self.assertTrue(Path(result["report_dir"]).name.endswith(".Report"))
        self.assertTrue(Path(result["model_dir"]).name.endswith(".SemanticModel"))

    def test_legacy_report_read_wrappers_delegate_to_new_report_tools(self) -> None:
        pages = powerbi_server.list_pages(str(FIXTURE_PROJECT_PATH))
        self.assertEqual(pages["count"], 13)
        self.assertEqual(pages["pages"][0]["id"], "ReportSectiona73ab10ffb0f4759f223")

        page = powerbi_server.get_page(str(FIXTURE_PROJECT_PATH), "ReportSectiona73ab10ffb0f4759f223")
        self.assertEqual(page["displayName"], "Time & material")

        visuals = powerbi_server.list_visuals(str(FIXTURE_PROJECT_PATH), "ReportSectiona73ab10ffb0f4759f223")
        self.assertEqual(visuals["count"], 17)

        visual = powerbi_server.get_visual(
            str(FIXTURE_PROJECT_PATH),
            "ReportSectiona73ab10ffb0f4759f223",
            "080c3bdfee4f864670b1",
        )
        self.assertEqual(visual["visual"]["visualType"], "slicer")


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import shutil
import unittest
import uuid
import json

from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.model.read import model_list_tables, model_list_measures
from powerbi_mcp.model.write import model_create_table
from powerbi_mcp.report.read import report_list_pages, report_list_visuals
from powerbi_mcp.visual_ai.pipeline import report_create_from_datasource_spec
from powerbi_mcp.validation.engine import validate_project

FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("pipeline_tests")

class PipelineTests(unittest.TestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_model_create_table_creates_table_tmdl_and_registers_in_model(self) -> None:
        project_dir = self.make_fixture_copy()

        columns = [
            {"name": "Opportunity ID", "dataType": "string"},
            {"name": "Estimated Value", "dataType": "double", "summarizeBy": "sum"}
        ]
        source_expr = (
            "let\n"
            "    Source = CommonDataService.Database(\"https://org.crm.dynamics.com/\"),\n"
            "    Navigation = Source{[Schema=\"dbo\",Item=\"opportunities\"]}[Data]\n"
            "in\n"
            "    Navigation"
        )

        result = model_create_table(
            project_path=str(project_dir),
            table_name="Dataverse_Opportunities",
            columns=columns,
            source_expression=source_expr,
            query_group="DataModel",
            dry_run=False
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "created")

        # Verify table exists in listing
        tables = model_list_tables(str(project_dir))
        table_names = [t["name"] for t in tables["tables"]]
        self.assertIn("Dataverse_Opportunities", table_names)

        # Verify table.tmdl file is created and has correct contents
        table_file = project_dir / "Focus.SemanticModel" / "definition" / "tables" / "Dataverse_Opportunities.tmdl"
        self.assertTrue(table_file.exists())
        content = table_file.read_text(encoding="utf-8")
        self.assertIn("table Dataverse_Opportunities", content)
        self.assertIn("column 'Opportunity ID'", content)
        self.assertIn("dataType: double", content)
        self.assertIn("summarizeBy: sum", content)
        self.assertIn("partition 'Dataverse_Opportunities-partition' = m", content)

        # Verify model.tmdl is updated
        model_file = project_dir / "Focus.SemanticModel" / "definition" / "model.tmdl"
        model_content = model_file.read_text(encoding="utf-8")
        self.assertIn("ref table Dataverse_Opportunities", model_content)

    def test_pipeline_dry_run_does_not_mutate_files(self) -> None:
        project_dir = self.make_fixture_copy()

        columns = [{"name": "Account ID", "dataType": "string"}]
        source_expr = "let Source = #\"Focus Sharepoint Link\" in Source"

        result = report_create_from_datasource_spec(
            project_path=str(project_dir),
            table_name="Dataverse_Accounts",
            columns=columns,
            source_expression=source_expr,
            measures=[{"name": "Total Account Count", "expression": "COUNTROWS('Dataverse_Accounts')"}],
            page_name="Accounts Dashboard",
            visuals_spec=[
                {
                    "visual_type": "card",
                    "title": "KPI Accounts",
                    "x": 10,
                    "y": 10,
                    "width": 200,
                    "height": 100,
                    "measure_entity": "Dataverse_Accounts",
                    "measure_property": "Total Account Count"
                }
            ],
            dry_run=True
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])

        # Check that table doesn't exist
        tables = model_list_tables(str(project_dir))
        table_names = [t["name"] for t in tables["tables"]]
        self.assertNotIn("Dataverse_Accounts", table_names)

    def test_pipeline_full_run_creates_model_measures_page_and_visuals(self) -> None:
        project_dir = self.make_fixture_copy()

        columns = [
            {"name": "Account ID", "dataType": "string"},
            {"name": "Account Value", "dataType": "double", "summarizeBy": "sum"}
        ]
        source_expr = (
            "let\n"
            "    Source = Excel.Workbook(Web.Contents(#\"Focus Sharepoint Link\")),\n"
            "    Accounts_Table = Source{[Item=\"Accounts\",Kind=\"Table\"]}[Data]\n"
            "in\n"
            "    Accounts_Table"
        )

        measures = [
            {"name": "Total Account Count", "expression": "COUNTROWS('Dataverse_Accounts')"},
            {"name": "Total Account Value", "expression": "SUM('Dataverse_Accounts'[Account Value])"}
        ]

        visuals = [
            {
                "visual_type": "card",
                "title": "Total Accounts",
                "x": 50,
                "y": 50,
                "width": 200,
                "height": 100,
                "measure_entity": "Dataverse_Accounts",
                "measure_property": "Total Account Count"
            },
            {
                "visual_type": "clusteredColumnChart",
                "title": "Account Values Chart",
                "x": 50,
                "y": 200,
                "width": 500,
                "height": 300,
                "category_entity": "Dataverse_Accounts",
                "category_property": "Account ID",
                "measure_entity": "Dataverse_Accounts",
                "measure_property": "Total Account Value"
            }
        ]

        result = report_create_from_datasource_spec(
            project_path=str(project_dir),
            table_name="Dataverse_Accounts",
            columns=columns,
            source_expression=source_expr,
            query_group="DataModel",
            measures=measures,
            page_name="Accounts Overview",
            visuals_spec=visuals,
            dry_run=False
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["dry_run"])

        # 1. Verify Table
        tables = model_list_tables(str(project_dir))
        table_names = [t["name"] for t in tables["tables"]]
        self.assertIn("Dataverse_Accounts", table_names)

        # 2. Verify Measures
        m_list = model_list_measures(str(project_dir))
        m_names = [m["name"] for m in m_list["measures"] if m["table"] == "Dataverse_Accounts"]
        self.assertIn("Total Account Count", m_names)
        self.assertIn("Total Account Value", m_names)

        # 3. Verify Page
        pages = report_list_pages(str(project_dir))
        page_dict = {p["displayName"]: p["id"] for p in pages["pages"]}
        self.assertIn("Accounts Overview", page_dict)
        page_id = page_dict["Accounts Overview"]

        # 4. Verify Visuals
        v_list = report_list_visuals(str(project_dir), page_id)
        self.assertEqual(v_list["count"], 2)
        visual_types = [v["visualType"] for v in v_list["visuals"]]
        self.assertIn("card", visual_types)
        self.assertIn("clusteredColumnChart", visual_types)

        # 5. Project validation checks (reachability and coherence)
        val_report = validate_project(str(project_dir))
        self.assertTrue(val_report.ok, f"Project validation failed: {[i.message for i in val_report.issues]}")

if __name__ == "__main__":
    unittest.main()

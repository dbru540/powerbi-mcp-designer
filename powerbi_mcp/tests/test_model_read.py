from pathlib import Path
import json
import shutil
import unittest
import uuid

from powerbi_mcp.model.read import (
    model_get_summary,
    model_list_measures,
    model_list_relationships,
    model_list_tables,
)
from powerbi_mcp.tests._temp_roots import named_temp_root


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("model_read")


class ModelReadTests(unittest.TestCase):
    def make_temp_project_dir(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        project_dir.mkdir()
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_model_get_summary_returns_fixture_metadata(self) -> None:
        summary = model_get_summary(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(summary["model_name"], "Model")
        self.assertEqual(summary["culture"], "en-US")
        self.assertEqual(summary["source_query_culture"], "en-US")
        self.assertEqual(summary["table_count"], 11)
        self.assertEqual(summary["relationship_count"], 11)
        self.assertEqual(summary["measure_count"], 61)
        self.assertEqual(summary["role_count"], 3)
        self.assertEqual(
            summary["roles"],
            ["Customer - Times off", "Customer", "PwC - Project priced"],
        )
        self.assertIn("Projects", summary["tables"])
        self.assertIn("Budgeted tickets", summary["tables"])

    def test_model_list_tables_returns_fixture_tables(self) -> None:
        result = model_list_tables(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(result["count"], 11)

        tables_by_name = {table["name"]: table for table in result["tables"]}
        self.assertIn("Budget", tables_by_name)
        self.assertIn("Power BI - All projects", tables_by_name)
        self.assertTrue(
            Path(tables_by_name["Budget"]["path"]).parts[-3:]
            == ("definition", "tables", "Budget.tmdl")
        )

    def test_model_list_relationships_returns_fixture_relationships(self) -> None:
        result = model_list_relationships(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(result["count"], 11)

        relationship = result["relationships"][0]
        self.assertEqual(relationship["name"], "cf50e31d-4394-349a-725f-e7601df160f1")
        self.assertEqual(relationship["from_table"], "Calendar")
        self.assertEqual(relationship["from_column"], "Date")
        self.assertEqual(relationship["to_table"], "Jo Time Per Location")
        self.assertEqual(relationship["to_column"], "Date")
        self.assertTrue(relationship["is_active"])
        self.assertEqual(relationship["cross_filtering_behavior"], "bothDirections")
        self.assertEqual(relationship["from_cardinality"], "one")
        self.assertTrue(
            Path(relationship["path"]).parts[-2:]
            == ("definition", "relationships.tmdl")
        )

    def test_model_list_measures_returns_fixture_measure_catalog(self) -> None:
        result = model_list_measures(str(FIXTURE_PROJECT_PATH))

        self.assertEqual(result["count"], 61)

        measures = {(measure["table"], measure["name"]): measure for measure in result["measures"]}
        self.assertIn(("Budget", "Budget"), measures)
        self.assertIn(("Budgeted tickets", "Fixed price - Budget amount"), measures)
        self.assertIn(("DevOps_Timesheets", "Billable amount"), measures)
        self.assertEqual(measures[("Budget", "Budget")]["display_folder"], "1 - Measures")
        self.assertTrue(
            measures[("Budget", "Budget")]["expression"].startswith("CALCULATE(")
        )
        self.assertTrue(
            Path(measures[("Budget", "Budget")]["path"]).parts[-3:]
            == ("definition", "tables", "Budget.tmdl")
        )

    def test_model_list_measures_skips_nested_metadata_subtrees(self) -> None:
        project_dir = self.make_temp_project_dir()
        tables_dir = project_dir / "Scratch.SemanticModel" / "definition" / "tables"
        tables_dir.mkdir(parents=True)
        (tables_dir / "NestedMetadata.tmdl").write_text(
            "\n".join(
                [
                    "table NestedMetadata",
                    "\tmeasure 'Fancy Measure' =",
                    "\t\t\tSUM(NestedMetadata[Amount])",
                    "\t\tformatStringDefinition = ```",
                    "\t\t\tsection1 = 0.0",
                    "\t\t\tsection2 = 0.0",
                    "\t\t```",
                    "\t\tdisplayFolder: Formatting",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        result = model_list_measures(str(project_dir))

        self.assertEqual(result["count"], 1)
        measure = result["measures"][0]
        self.assertEqual(measure["name"], "Fancy Measure")
        self.assertEqual(measure["expression"], "SUM(NestedMetadata[Amount])")
        self.assertEqual(measure["display_folder"], "Formatting")
        self.assertNotIn("formatStringDefinition", measure["expression"])
        self.assertNotIn("section1", measure["expression"])

    def test_bim_model_readers_return_tables_relationships_and_measures(self) -> None:
        project_dir = self.make_temp_project_dir()
        model_dir = project_dir / "Scratch.SemanticModel"
        model_dir.mkdir(parents=True)
        (project_dir / "Scratch.pbip").write_text("{}", encoding="utf-8")
        (model_dir / "model.bim").write_text(
            json.dumps(
                {
                    "model": {
                        "name": "BimModel",
                        "culture": "fr-FR",
                        "tables": [
                            {
                                "name": "Customers",
                                "columns": [{"name": "ClientName"}],
                            },
                            {
                                "name": "Measures",
                                "measures": [
                                    {
                                        "name": "Total Sales",
                                        "expression": "SUM(Facts[Amount])",
                                        "displayFolder": "Sales",
                                    }
                                ],
                            },
                        ],
                        "relationships": [
                            {
                                "name": "rel1",
                                "fromTable": "Facts",
                                "fromColumn": "CustomerId",
                                "toTable": "Customers",
                                "toColumn": "CustomerId",
                                "isActive": True,
                                "crossFilteringBehavior": "bothDirections",
                                "fromCardinality": "many",
                            }
                        ],
                        "roles": [{"name": "Reader"}],
                    }
                }
            ),
            encoding="utf-8",
        )

        tables = model_list_tables(str(project_dir))
        relationships = model_list_relationships(str(project_dir))
        measures = model_list_measures(str(project_dir))
        summary = model_get_summary(str(project_dir))

        self.assertEqual(tables["count"], 2)
        self.assertEqual([table["name"] for table in tables["tables"]], ["Customers", "Measures"])
        self.assertEqual(relationships["count"], 1)
        self.assertEqual(relationships["relationships"][0]["from_table"], "Facts")
        self.assertEqual(measures["count"], 1)
        self.assertEqual(measures["measures"][0]["name"], "Total Sales")
        self.assertEqual(measures["measures"][0]["display_folder"], "Sales")
        self.assertEqual(summary["model_name"], "BimModel")
        self.assertEqual(summary["culture"], "fr-FR")
        self.assertEqual(summary["table_count"], 2)
        self.assertEqual(summary["relationship_count"], 1)
        self.assertEqual(summary["measure_count"], 1)
        self.assertEqual(summary["role_count"], 1)


if __name__ == "__main__":
    unittest.main()

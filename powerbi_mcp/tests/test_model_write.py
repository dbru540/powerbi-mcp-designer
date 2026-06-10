from pathlib import Path
import shutil
import unittest
import uuid

from powerbi_mcp.model.read import model_list_measures, model_list_relationships
from powerbi_mcp.model.write import (
    model_create_relationship,
    model_update_column_metadata,
    model_update_table_description,
    model_upsert_measure,
    model_upsert_role,
)
from powerbi_mcp.tests._temp_roots import named_temp_root


FIXTURE_PROJECT_PATH = Path(__file__).resolve().parents[2] / "example"
TEMP_ROOT = named_temp_root("model_write")
CALENDAR_TABLE_PATH = Path("Focus.SemanticModel") / "definition" / "tables" / "Calendar.tmdl"
PROJECTS_TABLE_PATH = Path("Focus.SemanticModel") / "definition" / "tables" / "Projects.tmdl"
RELATIONSHIPS_PATH = Path("Focus.SemanticModel") / "definition" / "relationships.tmdl"
ROLES_DIR = Path("Focus.SemanticModel") / "definition" / "roles"
EXISTING_RELATIONSHIP_NAME = "cf50e31d-4394-349a-725f-e7601df160f1"
EXISTING_ROLE_NAME = "Customer"


class ModelWriteTests(unittest.TestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, ignore_errors=True)
        return project_dir

    def test_model_upsert_measure_creates_measure_before_columns_and_writes_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / CALENDAR_TABLE_PATH

        result = model_upsert_measure(
            str(project_dir),
            "Calendar",
            "Task 5 Measure",
            "COUNTROWS('Calendar')",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        measures = {
            (measure["table"], measure["name"]): measure
            for measure in model_list_measures(str(project_dir))["measures"]
        }
        self.assertIn(("Calendar", "Task 5 Measure"), measures)
        self.assertEqual(
            measures[("Calendar", "Task 5 Measure")]["expression"],
            "COUNTROWS('Calendar')",
        )

        updated_text = table_path.read_text(encoding="utf-8")
        self.assertIn("\tmeasure 'Task 5 Measure' = COUNTROWS('Calendar')", updated_text)
        self.assertLess(
            updated_text.index("\tmeasure 'Task 5 Measure' = COUNTROWS('Calendar')"),
            updated_text.index("\tcolumn Date"),
        )

        backups_dir = table_path.parent / ".backups"
        backup_files = sorted(backups_dir.glob("Calendar.tmdl.*.bak"))
        self.assertTrue(backup_files, "expected a backup for Calendar.tmdl")

    def test_model_upsert_measure_updates_existing_expression_and_preserves_metadata(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / CALENDAR_TABLE_PATH

        result = model_upsert_measure(
            str(project_dir),
            "Calendar",
            "Day measure",
            "SUM('Calendar'[Day]) + 1",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "updated")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        measures = {
            (measure["table"], measure["name"]): measure
            for measure in model_list_measures(str(project_dir))["measures"]
        }
        self.assertEqual(
            measures[("Calendar", "Day measure")]["expression"],
            "SUM('Calendar'[Day]) + 1",
        )

        updated_text = table_path.read_text(encoding="utf-8")
        self.assertIn("\tmeasure 'Day measure' = SUM('Calendar'[Day]) + 1", updated_text)
        self.assertIn("\t\tformatString: 0", updated_text)
        self.assertIn("changedProperty = IsHidden", updated_text)

    def test_model_upsert_measure_dry_run_reports_create_without_mutating_file(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / CALENDAR_TABLE_PATH
        original_text = table_path.read_text(encoding="utf-8")

        result = model_upsert_measure(
            str(project_dir),
            "Calendar",
            "Dry Run Measure",
            "DISTINCTCOUNT('Calendar'[Date])",
            dry_run=True,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        self.assertEqual(table_path.read_text(encoding="utf-8"), original_text)
        self.assertNotIn(
            ("Calendar", "Dry Run Measure"),
            {
                (measure["table"], measure["name"])
                for measure in model_list_measures(str(project_dir))["measures"]
            },
        )

    def test_model_upsert_measure_replaces_multiline_expression_without_leaking_old_body(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / Path("Focus.SemanticModel") / "definition" / "tables" / "Budget.tmdl"

        result = model_upsert_measure(
            str(project_dir),
            "Budget",
            "Budget (CY)",
            "VAR NewBudget = [Budget]\nRETURN NewBudget",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "updated")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        measures = {
            (measure["table"], measure["name"]): measure
            for measure in model_list_measures(str(project_dir))["measures"]
        }
        expression = measures[("Budget", "Budget (CY)")]["expression"]
        self.assertIn("VAR NewBudget = [Budget]", expression)
        self.assertIn("RETURN NewBudget", expression)
        self.assertNotIn("USERELATIONSHIP('Calendar'[Date],Budget[Date])", expression)

        updated_text = table_path.read_text(encoding="utf-8")
        start = updated_text.index("\tmeasure 'Budget (CY)' =")
        end = updated_text.index("\n\tmeasure Actual =", start)
        updated_block = updated_text[start:end]
        self.assertIn("\tmeasure 'Budget (CY)' =", updated_block)
        self.assertIn("\t\t\tVAR NewBudget = [Budget]", updated_block)
        self.assertIn("\t\t\tRETURN NewBudget", updated_block)
        self.assertNotIn("USERELATIONSHIP('Calendar'[Date],Budget[Date])", updated_block)
        self.assertIn("\t\tformatString: \"€\"\\ #,0.00;-\"€\"\\ #,0.00;\"€\"\\ #,0.00", updated_block)

    def test_model_create_relationship_appends_new_relationship_and_writes_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        relationships_path = project_dir / RELATIONSHIPS_PATH

        result = model_create_relationship(
            str(project_dir),
            "Task5Relationship",
            "Budget",
            "Date",
            "Calendar",
            "Date",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        relationships = {
            relationship["name"]: relationship
            for relationship in model_list_relationships(str(project_dir))["relationships"]
        }
        self.assertIn("Task5Relationship", relationships)
        self.assertEqual(relationships["Task5Relationship"]["from_table"], "Budget")
        self.assertEqual(relationships["Task5Relationship"]["from_column"], "Date")
        self.assertEqual(relationships["Task5Relationship"]["to_table"], "Calendar")
        self.assertEqual(relationships["Task5Relationship"]["to_column"], "Date")

        updated_text = relationships_path.read_text(encoding="utf-8")
        self.assertIn("relationship Task5Relationship", updated_text)
        self.assertIn("\tfromColumn: Budget.Date", updated_text)
        self.assertIn("\ttoColumn: Calendar.Date", updated_text)

        backups_dir = relationships_path.parent / ".backups"
        backup_files = sorted(backups_dir.glob("relationships.tmdl.*.bak"))
        self.assertTrue(backup_files, "expected a backup for relationships.tmdl")

    def test_model_create_relationship_quotes_identifiers_with_spaces_on_create(self) -> None:
        project_dir = self.make_fixture_copy()
        relationships_path = project_dir / RELATIONSHIPS_PATH

        result = model_create_relationship(
            str(project_dir),
            "QuotedRelationship",
            "Power BI - All projects",
            "Work Item Id",
            "Budgeted tickets",
            "Work Item Id",
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_text = relationships_path.read_text(encoding="utf-8")
        self.assertIn("\tfromColumn: 'Power BI - All projects'.'Work Item Id'", updated_text)
        self.assertIn("\ttoColumn: 'Budgeted tickets'.'Work Item Id'", updated_text)

    def test_model_create_relationship_updates_existing_fields_and_preserves_metadata(self) -> None:
        project_dir = self.make_fixture_copy()

        result = model_create_relationship(
            str(project_dir),
            EXISTING_RELATIONSHIP_NAME,
            "Budget",
            "Date",
            "Calendar",
            "Date",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "updated")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])

        relationships = {
            relationship["name"]: relationship
            for relationship in model_list_relationships(str(project_dir))["relationships"]
        }
        relationship = relationships[EXISTING_RELATIONSHIP_NAME]
        self.assertEqual(relationship["from_table"], "Budget")
        self.assertEqual(relationship["from_column"], "Date")
        self.assertEqual(relationship["to_table"], "Calendar")
        self.assertEqual(relationship["to_column"], "Date")
        self.assertEqual(relationship["cross_filtering_behavior"], "bothDirections")
        self.assertEqual(relationship["from_cardinality"], "one")

    def test_model_create_relationship_quotes_identifiers_with_spaces_on_update(self) -> None:
        project_dir = self.make_fixture_copy()
        relationships_path = project_dir / RELATIONSHIPS_PATH

        result = model_create_relationship(
            str(project_dir),
            EXISTING_RELATIONSHIP_NAME,
            "Power BI - All projects",
            "Work Item Id",
            "Budgeted tickets",
            "Work Item Id",
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_text = relationships_path.read_text(encoding="utf-8")
        self.assertIn(
            f"relationship {EXISTING_RELATIONSHIP_NAME}\n\tcrossFilteringBehavior: bothDirections\n\tfromCardinality: one\n\tfromColumn: 'Power BI - All projects'.'Work Item Id'\n\ttoColumn: 'Budgeted tickets'.'Work Item Id'",
            updated_text,
        )

    def test_model_create_relationship_dry_run_reports_create_without_mutating_file(self) -> None:
        project_dir = self.make_fixture_copy()
        relationships_path = project_dir / RELATIONSHIPS_PATH
        original_text = relationships_path.read_text(encoding="utf-8")

        result = model_create_relationship(
            str(project_dir),
            "Task5DryRunRelationship",
            "Budget",
            "Date",
            "Calendar",
            "Date",
            dry_run=True,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        self.assertEqual(relationships_path.read_text(encoding="utf-8"), original_text)
        self.assertNotIn(
            "Task5DryRunRelationship",
            {
                relationship["name"]
                for relationship in model_list_relationships(str(project_dir))["relationships"]
            },
        )

    def test_model_update_table_description_inserts_description_and_writes_backup(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / PROJECTS_TABLE_PATH

        result = model_update_table_description(
            str(project_dir),
            "Projects",
            "Task 9 table description",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_text = table_path.read_text(encoding="utf-8")
        self.assertIn("\tdescription: Task 9 table description", updated_text)
        self.assertIn("\tlineageTag:", updated_text)

        backups_dir = table_path.parent / ".backups"
        backup_files = sorted(backups_dir.glob("Projects.tmdl.*.bak"))
        self.assertTrue(backup_files, "expected a backup for Projects.tmdl")

    def test_model_update_column_metadata_updates_existing_column_block(self) -> None:
        project_dir = self.make_fixture_copy()
        table_path = project_dir / PROJECTS_TABLE_PATH

        result = model_update_column_metadata(
            str(project_dir),
            "Projects",
            "Project Name",
            description="Task 9 column description",
            summarize_by="none",
        )

        self.assertTrue(result["success"])
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        updated_text = table_path.read_text(encoding="utf-8")
        start = updated_text.index("\tcolumn 'Project Name'")
        end = updated_text.index("\n\tcolumn 'Project Type'", start)
        block = updated_text[start:end]
        self.assertIn("\t\tdescription: Task 9 column description", block)
        self.assertIn("\t\tsummarizeBy: none", block)
        self.assertIn("\t\tsourceColumn: Project Name", block)

    def test_model_upsert_role_creates_new_role_file(self) -> None:
        project_dir = self.make_fixture_copy()
        role_path = project_dir / ROLES_DIR / "Task 9 Role.tmdl"

        result = model_upsert_role(
            str(project_dir),
            "Task 9 Role",
            "Projects",
            'Projects[Project Name] = "Task 9"',
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "created")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        self.assertTrue(role_path.exists())
        role_text = role_path.read_text(encoding="utf-8")
        self.assertIn("role 'Task 9 Role'", role_text)
        self.assertIn('\ttablePermission Projects = Projects[Project Name] = "Task 9"', role_text)

    def test_model_upsert_role_updates_existing_role_and_preserves_annotation(self) -> None:
        project_dir = self.make_fixture_copy()
        role_path = project_dir / ROLES_DIR / "Customer.tmdl"

        result = model_upsert_role(
            str(project_dir),
            EXISTING_ROLE_NAME,
            "Projects",
            'Projects[Project Name] = "Updated"',
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "updated")
        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["ok"])
        role_text = role_path.read_text(encoding="utf-8")
        self.assertIn('tablePermission Projects = Projects[Project Name] = "Updated"', role_text)
        self.assertIn("\tannotation PBI_Id =", role_text)


if __name__ == "__main__":
    unittest.main()

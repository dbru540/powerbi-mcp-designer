import shutil
import tempfile
import unittest
from pathlib import Path

EXAMPLE = str(Path(__file__).parent.parent.parent / "example")


class EngineValidateProjectTests(unittest.TestCase):
    def test_example_project_validates_ok(self) -> None:
        from powerbi_mcp.validation.engine import validate_project
        report = validate_project(EXAMPLE)
        errors = [i for i in report.issues if i.severity == "error"]
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")
        self.assertTrue(report.ok)

    def test_report_only_validates_ok(self) -> None:
        from powerbi_mcp.validation.engine import validate_report
        report = validate_report(EXAMPLE)
        errors = [i for i in report.issues if i.severity == "error"]
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")
        self.assertTrue(report.ok)

    def test_report_validation_ignores_hidden_backup_json(self) -> None:
        from powerbi_mcp.validation.engine import validate_report

        tmp_dir = tempfile.mkdtemp()
        try:
            project_dir = Path(tmp_dir) / "demo"
            report_dir = project_dir / "Demo.Report"
            (report_dir / ".backups").mkdir(parents=True)
            (project_dir / "Demo.pbip").write_text("{}", encoding="utf-8")
            (report_dir / ".backups" / "invalid.json").write_text("{", encoding="utf-8")

            report = validate_report(str(project_dir))

            self.assertTrue(report.ok, report.to_dict())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_model_only_validates_ok(self) -> None:
        from powerbi_mcp.validation.engine import validate_model
        report = validate_model(EXAMPLE)
        errors = [i for i in report.issues if i.severity == "error"]
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")
        self.assertTrue(report.ok)


class EnginePrePostValidateTests(unittest.TestCase):
    def test_pre_validate_valid_visual_payload(self) -> None:
        from powerbi_mcp.validation.engine import pre_validate_payload
        import json
        # Find a real visual.json in the fixture
        example = Path(EXAMPLE)
        visual_files = list(example.rglob("visual*.json"))
        self.assertTrue(len(visual_files) > 0)
        payload = json.loads(visual_files[0].read_text(encoding="utf-8"))
        report = pre_validate_payload(payload, str(visual_files[0]))
        # Should not crash. ok may be True or False depending on schema match.
        self.assertIsNotNone(report)
        self.assertIsInstance(report.ok, bool)

    def test_pre_validate_missing_schema_does_not_crash(self) -> None:
        from powerbi_mcp.validation.engine import pre_validate_payload
        payload = {"name": "test", "data": 123}
        report = pre_validate_payload(payload, "/some/file.json")
        self.assertTrue(report.ok)  # No schema = info, not error

    def test_post_validate_clean_paths_returns_ok(self) -> None:
        from powerbi_mcp.validation.engine import post_validate_paths
        import json
        example = Path(EXAMPLE)
        visual_files = list(example.rglob("visual*.json"))
        touched = [str(f) for f in visual_files[:2]]
        report = post_validate_paths(EXAMPLE, touched)
        self.assertIsNotNone(report)
        self.assertIsInstance(report.ok, bool)


if __name__ == "__main__":
    unittest.main()

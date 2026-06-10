import json
import shutil
import tempfile
import unittest
from pathlib import Path


class ReachabilityValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        example = Path(__file__).parent.parent.parent / "example"
        shutil.copytree(str(example), str(Path(self.tmp_dir) / "example"))
        self.project_path = str(Path(self.tmp_dir) / "example")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clean_fixture_passes_reachability(self) -> None:
        from powerbi_mcp.validation.reachability import validate_reachability
        report = validate_reachability(self.project_path)
        errors = [i for i in report.issues if i.code == "REACH_UNRESOLVED_BINDING"]
        self.assertEqual(errors, [], f"Unexpected REACH_UNRESOLVED_BINDING: {errors}")

    def test_visual_binding_to_nonexistent_entity_produces_error(self) -> None:
        from powerbi_mcp.validation.reachability import validate_reachability
        # Find a visual.json in the example
        example_dir = Path(self.project_path)
        visual_files = list(example_dir.rglob("visual.json"))
        self.assertTrue(len(visual_files) > 0, "No visual.json found in fixture")

        target = visual_files[0]
        data = json.loads(target.read_text(encoding="utf-8"))

        # Inject a fake binding using the same structure _extract_query_state_bindings reads
        if "visual" not in data:
            data["visual"] = {}
        if "query" not in data["visual"]:
            data["visual"]["query"] = {}
        if "queryState" not in data["visual"]["query"]:
            data["visual"]["query"]["queryState"] = {}

        data["visual"]["query"]["queryState"]["Values"] = {
            "projections": [
                {
                    "field": {
                        "Column": {
                            "Expression": {
                                "SourceRef": {
                                    "Entity": "NonExistentEntity"
                                }
                            },
                            "Property": "FakeMeasure"
                        }
                    },
                    "queryRef": "NonExistentEntity.FakeMeasure",
                    "nativeQueryRef": "FakeMeasure"
                }
            ]
        }
        target.write_text(json.dumps(data), encoding="utf-8")

        report = validate_reachability(self.project_path)
        codes = [i.code for i in report.issues]
        self.assertIn("REACH_UNRESOLVED_BINDING", codes)

    def test_bim_model_bindings_are_reachable(self) -> None:
        from powerbi_mcp.validation.reachability import validate_reachability

        project_dir = Path(self.tmp_dir) / "bim_project"
        report_dir = project_dir / "Demo.Report" / "definition" / "pages"
        visuals_dir = report_dir / "p1" / "visuals" / "v1"
        model_dir = project_dir / "Demo.SemanticModel"
        visuals_dir.mkdir(parents=True)
        model_dir.mkdir(parents=True)

        (project_dir / "Demo.pbip").write_text("{}", encoding="utf-8")
        (report_dir / "pages.json").write_text(json.dumps({"pageOrder": ["p1"]}), encoding="utf-8")
        (report_dir / "p1" / "page.json").write_text(json.dumps({"name": "p1"}), encoding="utf-8")
        (visuals_dir / "visual.json").write_text(
            json.dumps(
                {
                    "visual": {
                        "query": {
                            "queryState": {
                                "Category": {
                                    "projections": [
                                        {
                                            "field": {
                                                "Column": {
                                                    "Expression": {"SourceRef": {"Entity": "Customers"}},
                                                    "Property": "ClientName",
                                                }
                                            },
                                            "queryRef": "Customers.ClientName",
                                        }
                                    ]
                                },
                                "Y": {
                                    "projections": [
                                        {
                                            "field": {
                                                "Measure": {
                                                    "Expression": {"SourceRef": {"Entity": "Measures"}},
                                                    "Property": "Total Sales",
                                                }
                                            },
                                            "queryRef": "Measures.Total Sales",
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (model_dir / "model.bim").write_text(
            json.dumps(
                {
                    "model": {
                        "tables": [
                            {"name": "Customers", "columns": [{"name": "ClientName"}]},
                            {"name": "Measures", "measures": [{"name": "Total Sales"}]},
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        report = validate_reachability(str(project_dir))

        self.assertTrue(report.ok, report.to_dict())

    def test_hidden_backup_visuals_are_ignored(self) -> None:
        from powerbi_mcp.validation.reachability import validate_reachability

        project_dir = Path(self.tmp_dir) / "backup_project"
        tables_dir = project_dir / "Demo.SemanticModel" / "definition" / "tables"
        page_dir = project_dir / "Demo.Report" / "definition" / "pages" / "p1"
        active_visual = page_dir / "visuals" / "v1"
        backup_visual = page_dir / "visuals" / ".backups" / "old" / "bad"
        tables_dir.mkdir(parents=True)
        active_visual.mkdir(parents=True)
        backup_visual.mkdir(parents=True)

        (project_dir / "Demo.pbip").write_text("{}", encoding="utf-8")
        (page_dir.parent / "pages.json").write_text(json.dumps({"pageOrder": ["p1"]}), encoding="utf-8")
        (page_dir / "page.json").write_text(json.dumps({"name": "p1"}), encoding="utf-8")
        (tables_dir / "Facts.tmdl").write_text("\ttable Facts\n\t\tcolumn Amount\n", encoding="utf-8")
        (active_visual / "visual.json").write_text(json.dumps({"visual": {}}), encoding="utf-8")
        (backup_visual / "visual.json").write_text(
            json.dumps(
                {
                    "visual": {
                        "query": {
                            "queryState": {
                                "Values": {
                                    "projections": [
                                        {
                                            "field": {
                                                "Column": {
                                                    "Expression": {"SourceRef": {"Entity": "Missing"}},
                                                    "Property": "Bad",
                                                }
                                            },
                                            "queryRef": "Missing.Bad",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        report = validate_reachability(str(project_dir))

        self.assertTrue(report.ok, report.to_dict())


if __name__ == "__main__":
    unittest.main()

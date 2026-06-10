import json
import unittest
from pathlib import Path

from powerbi_mcp.validation.pbir import validate_pbir_payload, validate_pbir_file

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example" / "Focus.Report" / "definition"

VISUAL_PATHS = [
    EXAMPLE_DIR / "pages/15fe2ec320b2b5d1e78d/visuals/c92381d924b9e4208d19/visual.json",
    EXAMPLE_DIR / "pages/1b593cede641d04297cc/visuals/9fd0547670d1e5504c3a/visual.json",
    EXAMPLE_DIR / "pages/1b593cede641d04297cc/visuals/f7823281894d4c05b636/visual.json",
]

PAGE_PATHS = [
    EXAMPLE_DIR / "pages/15fe2ec320b2b5d1e78d/page.json",
    EXAMPLE_DIR / "pages/1b593cede641d04297cc/page.json",
    EXAMPLE_DIR / "pages/320d197c26a960f2dbde/page.json",
]

REPORT_PATH = EXAMPLE_DIR / "report.json"
SCHEMA_INDEX_PATH = Path(__file__).parent.parent / "validation" / "schemas" / "INDEX.json"

VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/visualContainer/2.4.0/schema.json"
)


class TestValidPbir(unittest.TestCase):
    def test_schema_index_includes_desktop_generated_versions(self) -> None:
        index = json.loads(SCHEMA_INDEX_PATH.read_text(encoding="utf-8"))

        self.assertIn(
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
            index,
        )
        self.assertIn(
            "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
            index,
        )

    def test_valid_visual_json_passes(self) -> None:
        for path in VISUAL_PATHS:
            with self.subTest(path=str(path)):
                result = validate_pbir_file(path)
                self.assertTrue(
                    result.ok,
                    msg=f"{path.name} failed: {[i.message for i in result.issues if i.severity == 'error']}",
                )

    def test_valid_page_json_passes(self) -> None:
        for path in PAGE_PATHS:
            with self.subTest(path=str(path)):
                result = validate_pbir_file(path)
                self.assertTrue(
                    result.ok,
                    msg=f"{path.name} failed: {[i.message for i in result.issues if i.severity == 'error']}",
                )

    def test_valid_report_json_passes(self) -> None:
        result = validate_pbir_file(REPORT_PATH)
        self.assertTrue(
            result.ok,
            msg=f"report.json failed: {[i.message for i in result.issues if i.severity == 'error']}",
        )


class TestInvalidPbir(unittest.TestCase):
    def test_invalid_visual_payload_returns_errors(self) -> None:
        payload = {
            "$schema": VISUAL_SCHEMA,
            "name": "test_visual",
            "position": {
                "x": "not-a-number",  # should be number
                "y": 0,
                "z": 0,
                "height": 100,
                "width": 100,
                "tabOrder": 0,
            },
        }
        result = validate_pbir_payload(payload, "test_visual.json")
        self.assertFalse(result.ok)
        codes = [i.code for i in result.issues]
        self.assertIn("PBIR_SCHEMA_VIOLATION", codes)

    def test_unknown_schema_url_returns_loud_error(self) -> None:
        payload = {
            "$schema": "https://example.com/unknown-schema/99.0.0/schema.json",
            "name": "x",
        }
        result = validate_pbir_payload(payload, "unknown.json")
        self.assertFalse(result.ok)
        codes = [i.code for i in result.issues]
        self.assertIn("PBIR_UNKNOWN_SCHEMA", codes)
        # message should hint at how to refresh schemas
        messages = " ".join(i.message for i in result.issues)
        self.assertIn("refresh_pbir_schemas.py", messages)

    def test_missing_schema_field_returns_info(self) -> None:
        payload = {"name": "x", "position": {"x": 0, "y": 0}}
        result = validate_pbir_payload(payload, "no_schema.json")
        self.assertTrue(result.ok)
        codes = [i.code for i in result.issues]
        self.assertIn("PBIR_NO_SCHEMA", codes)
        severities = [i.severity for i in result.issues if i.code == "PBIR_NO_SCHEMA"]
        self.assertEqual(severities, ["info"])


class TestFileHelpers(unittest.TestCase):
    def test_missing_file_returns_error(self) -> None:
        result = validate_pbir_file("/nonexistent/path/visual.json")
        self.assertFalse(result.ok)
        codes = [i.code for i in result.issues]
        self.assertIn("PBIR_FILE_NOT_FOUND", codes)

    def test_invalid_json_returns_parse_error(self, tmp_path=None) -> None:
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("{ not valid json }")
            tmp = f.name
        try:
            result = validate_pbir_file(tmp)
            self.assertFalse(result.ok)
            codes = [i.code for i in result.issues]
            self.assertIn("PBIR_PARSE_ERROR", codes)
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()

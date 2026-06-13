from __future__ import annotations

import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

from scripts.check_distribution import (
    check_dist_artifacts,
    check_project_files,
    check_pyproject_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class DistributionCheckTests(unittest.TestCase):
    def test_project_distribution_files_are_present(self) -> None:
        result = check_project_files(REPO_ROOT)

        self.assertTrue(result.ok, result.messages)

    def test_pyproject_exposes_expected_console_tools(self) -> None:
        result = check_pyproject_metadata(REPO_ROOT / "pyproject.toml")

        self.assertTrue(result.ok, result.messages)

        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = pyproject["project"]
        self.assertEqual(project["name"], "powerbi-mcp-designer")
        self.assertEqual(project["version"], "0.2.1")
        self.assertEqual(
            project["scripts"]["powerbi-mcp-designer"],
            "powerbi_mcp.server:main",
        )

    def test_dist_artifact_check_rejects_wheel_with_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            wheel_path = dist_dir / "powerbi_mcp_designer-0.2.1-py3-none-any.whl"
            sdist_path = dist_dir / "powerbi_mcp_designer-0.2.1.tar.gz"
            sdist_path.write_bytes(b"placeholder")
            with zipfile.ZipFile(wheel_path, "w") as wheel:
                wheel.writestr("powerbi_mcp/tests/test_bad.py", "")
                wheel.writestr("powerbi_mcp/validation/schemas/INDEX.json", "{}")
                wheel.writestr("powerbi_mcp_designer-0.2.1.dist-info/entry_points.txt", "")

            result = check_dist_artifacts(dist_dir)

        self.assertFalse(result.ok)
        self.assertIn("must not include powerbi_mcp/tests", "\n".join(result.messages))


if __name__ == "__main__":
    unittest.main()

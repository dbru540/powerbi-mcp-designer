import shutil
import tempfile
import unittest
from pathlib import Path

from powerbi_mcp.validation.tmdl import validate_tmdl

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "example"


class TmdlValidationBaseCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        # copytree into a subdirectory so the layout mirrors the real fixture
        self.project_path = Path(self._tmpdir) / "example"
        shutil.copytree(str(FIXTURE_PATH), str(self.project_path))

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------ helpers

    def _definition_dir(self) -> Path:
        model_dir = next(
            (p for p in self.project_path.iterdir() if p.name.endswith(".SemanticModel")),
            None,
        )
        assert model_dir is not None, "No .SemanticModel dir found in fixture copy"
        return model_dir / "definition"

    def _tables_dir(self) -> Path:
        return self._definition_dir() / "tables"

    def _roles_dir(self) -> Path:
        return self._definition_dir() / "roles"

    def _relationships_path(self) -> Path:
        return self._definition_dir() / "relationships.tmdl"

    def _model_path(self) -> Path:
        return self._definition_dir() / "model.tmdl"

    def _error_codes(self, report) -> list[str]:
        return [i.code for i in report.issues if i.severity == "error"]


# ------------------------------------------------------------------ Rule 1: orphan refs

class TestOrphanRef(TmdlValidationBaseCase):
    def test_clean_fixture_passes(self) -> None:
        report = validate_tmdl(str(self.project_path))
        orphan_errors = [i for i in report.issues if i.code == "TMDL_ORPHAN_REF"]
        self.assertEqual(orphan_errors, [], msg=f"Unexpected TMDL_ORPHAN_REF issues: {orphan_errors}")

    def test_orphan_relationship_table_produces_error(self) -> None:
        rel_path = self._relationships_path()
        existing = rel_path.read_text(encoding="utf-8")
        rel_path.write_text(
            existing + "\nrelationship bad-ref-test\n\tfromColumn: NonExistentTable.Col\n\ttoColumn: Projects.'Project Name'\n",
            encoding="utf-8",
        )
        report = validate_tmdl(str(self.project_path))
        codes = self._error_codes(report)
        self.assertIn("TMDL_ORPHAN_REF", codes, msg=f"Expected TMDL_ORPHAN_REF, got issues: {report.issues}")


# ------------------------------------------------------------------ Rule 2: duplicates

class TestDuplicates(TmdlValidationBaseCase):
    def test_clean_fixture_has_no_duplicates(self) -> None:
        report = validate_tmdl(str(self.project_path))
        dup_errors = [i for i in report.issues if i.code == "TMDL_DUPLICATE"]
        self.assertEqual(dup_errors, [], msg=f"Unexpected TMDL_DUPLICATE issues: {dup_errors}")

    def test_duplicate_measure_name_produces_error(self) -> None:
        # Find a table that already has a measure and duplicate it
        tables_dir = self._tables_dir()
        # Budget.tmdl has measures — pick it
        budget_path = tables_dir / "Budget.tmdl"
        text = budget_path.read_text(encoding="utf-8")
        # Append a duplicate measure block at end
        budget_path.write_text(
            text.rstrip() + "\n\n\tmeasure 'DupMeasure' = 1\n\n\tmeasure 'DupMeasure' = 2\n",
            encoding="utf-8",
        )
        report = validate_tmdl(str(self.project_path))
        codes = self._error_codes(report)
        self.assertIn("TMDL_DUPLICATE", codes, msg=f"Expected TMDL_DUPLICATE, got issues: {report.issues}")


# ------------------------------------------------------------------ Rule 4: naming

class TestNaming(TmdlValidationBaseCase):
    def test_clean_fixture_has_no_naming_issues(self) -> None:
        report = validate_tmdl(str(self.project_path))
        bad_name_errors = [i for i in report.issues if i.code == "TMDL_BAD_NAME" and i.severity == "error"]
        self.assertEqual(bad_name_errors, [], msg=f"Unexpected TMDL_BAD_NAME errors: {bad_name_errors}")

    def test_empty_measure_name_produces_error(self) -> None:
        tables_dir = self._tables_dir()
        budget_path = tables_dir / "Budget.tmdl"
        text = budget_path.read_text(encoding="utf-8")
        # Append a measure with an empty-looking name (two spaces between 'measure' and '=')
        budget_path.write_text(
            text.rstrip() + "\n\n\tmeasure  = 1\n",
            encoding="utf-8",
        )
        report = validate_tmdl(str(self.project_path))
        bad_name_errors = [i for i in report.issues if i.code == "TMDL_BAD_NAME" and i.severity == "error"]
        self.assertTrue(
            len(bad_name_errors) > 0,
            msg=f"Expected TMDL_BAD_NAME error, got issues: {report.issues}",
        )


# ------------------------------------------------------------------ Rule 5: cross-file coherence

class TestCoherence(TmdlValidationBaseCase):
    def test_clean_fixture_passes_coherence(self) -> None:
        report = validate_tmdl(str(self.project_path))
        coherence_errors = [i for i in report.issues if i.code == "TMDL_COHERENCE"]
        self.assertEqual(coherence_errors, [], msg=f"Unexpected TMDL_COHERENCE issues: {coherence_errors}")

    def test_model_ref_to_missing_table_produces_error(self) -> None:
        model_path = self._model_path()
        existing = model_path.read_text(encoding="utf-8")
        model_path.write_text(
            existing.rstrip() + "\nref table 'Phantom Table'\n",
            encoding="utf-8",
        )
        report = validate_tmdl(str(self.project_path))
        codes = self._error_codes(report)
        self.assertIn("TMDL_ORPHAN_REF", codes, msg=f"Expected TMDL_ORPHAN_REF, got issues: {report.issues}")

    def test_role_referencing_nonexistent_table_produces_error(self) -> None:
        roles_dir = self._roles_dir()
        # Write a new role file that references a table that does not exist
        ghost_role_path = roles_dir / "GhostRole.tmdl"
        ghost_role_path.write_text(
            "role GhostRole\n\tmodelPermission: read\n\n\ttablePermission GhostTable = TRUE()\n",
            encoding="utf-8",
        )
        report = validate_tmdl(str(self.project_path))
        codes = self._error_codes(report)
        self.assertIn("TMDL_COHERENCE", codes, msg=f"Expected TMDL_COHERENCE, got issues: {report.issues}")


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
import tempfile

from powerbi_mcp.common.backups import backup_file, restore_from_backup


class BackupRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.original_file = Path(self.tmp_dir) / "test.json"
        self.original_file.write_text('{"version": 1}', encoding="utf-8")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_restore_from_backup_replaces_original_with_backup_bytes(self) -> None:
        backup_path = backup_file(self.original_file)
        self.original_file.write_text('{"version": 2, "corrupted": true}', encoding="utf-8")
        restore_from_backup(self.original_file, backup_path)
        restored_content = self.original_file.read_text(encoding="utf-8")
        self.assertEqual(restored_content, '{"version": 1}')

    def test_restore_from_backup_raises_on_missing_backup(self) -> None:
        with self.assertRaises(FileNotFoundError):
            restore_from_backup(self.original_file, "/nonexistent/backup.bak")

    def test_restore_from_backup_works_with_string_paths(self) -> None:
        backup_path = backup_file(str(self.original_file))
        self.original_file.write_text("corrupted", encoding="utf-8")
        restore_from_backup(str(self.original_file), backup_path)
        self.assertEqual(self.original_file.read_text(encoding="utf-8"), '{"version": 1}')

    def test_backup_file_contract_unchanged(self) -> None:
        backup_path = backup_file(self.original_file)
        self.assertTrue(backup_path.endswith(".bak"))
        self.assertIn(".backups", backup_path)
        self.assertTrue(Path(backup_path).exists())


if __name__ == "__main__":
    unittest.main()

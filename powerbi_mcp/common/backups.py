from datetime import datetime, UTC
from pathlib import Path


def backup_file(path: str | Path) -> str:
    target = Path(path)
    backups_dir = target.parent / ".backups"
    backups_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    backup_path = backups_dir / f"{target.name}.{timestamp}.bak"
    backup_path.write_bytes(target.read_bytes())
    return str(backup_path)


def restore_from_backup(original_path: str | Path, backup_path: str | Path) -> None:
    """Replace the original file with the bytes from its backup."""
    source = Path(backup_path)
    target = Path(original_path)
    if not source.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    target.write_bytes(source.read_bytes())

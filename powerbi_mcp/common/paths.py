from dataclasses import dataclass
from pathlib import Path

from .types import ProjectPathInput


@dataclass(frozen=True)
class ProjectPaths:
    project_dir: Path
    pbip_file: Path | None
    report_dir: Path | None
    model_dir: Path | None
    pages_dir: Path | None
    tables_dir: Path | None


def _coerce_project_dir(project_path: ProjectPathInput) -> Path:
    return Path(project_path)


def _find_first_matching_child(
    project_path: ProjectPathInput,
    *,
    predicate,
) -> Path | None:
    project_dir = _coerce_project_dir(project_path)
    if not project_dir.exists():
        return None

    for child in sorted(project_dir.iterdir()):
        if predicate(child):
            return child

    return None


def find_pbip_file(project_path: ProjectPathInput) -> Path | None:
    """Find the first `.pbip` file directly under a project directory."""
    return _find_first_matching_child(
        project_path,
        predicate=lambda child: child.is_file() and child.suffix == ".pbip",
    )


def find_report_dir(project_path: ProjectPathInput) -> Path | None:
    """Find the `.Report` directory directly under a project directory."""
    return _find_first_matching_child(
        project_path,
        predicate=lambda child: child.is_dir() and child.name.endswith(".Report"),
    )


def find_model_dir(project_path: ProjectPathInput) -> Path | None:
    """Find the `.SemanticModel` directory directly under a project directory."""
    return _find_first_matching_child(
        project_path,
        predicate=lambda child: child.is_dir()
        and child.name.endswith(".SemanticModel"),
    )


def _child_path(parent: Path | None, *parts: str) -> Path | None:
    if parent is None:
        return None

    return parent.joinpath(*parts)


def safe_child(parent: Path, *parts: str) -> Path:
    """Join path parts and verify the result stays within parent. Raises ValueError on traversal."""
    resolved = (parent / Path(*parts)).resolve()
    if not resolved.is_relative_to(parent.resolve()):
        raise ValueError(f"Path traversal detected: {'/'.join(parts)!r} escapes {parent}")
    return resolved


def get_project_summary_paths(project_path: ProjectPathInput) -> ProjectPaths:
    """Collect the shared project discovery paths used by the server."""
    project_dir = _coerce_project_dir(project_path)
    pbip_file = find_pbip_file(project_dir)
    report_dir = find_report_dir(project_dir)
    model_dir = find_model_dir(project_dir)

    return ProjectPaths(
        project_dir=project_dir,
        pbip_file=pbip_file,
        report_dir=report_dir,
        model_dir=model_dir,
        pages_dir=_child_path(report_dir, "definition", "pages"),
        tables_dir=_child_path(model_dir, "definition", "tables"),
    )

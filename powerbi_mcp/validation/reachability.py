from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from powerbi_mcp.analysis.bindings import _extract_query_state_bindings
from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.model.read import _strip_quotes
from powerbi_mcp.validation.report import ValidationIssue, ValidationReport


# Matches: \tcolumn 'Quoted Name' or \tcolumn Name (with optional = expression)
_COLUMN_RE = re.compile(r"^\tcolumn\s+(?P<name>(?:'[^']*'|[^=\s][^=\n]*?))\s*(?:=|$)")
_MEASURE_RE = re.compile(r"^\tmeasure\s+(?P<name>'.+?'|[^\n=]+?)\s*=")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_model_catalog(project_path: str) -> set[tuple[str, str]]:
    """Return a set of (entity, property) tuples from the semantic model."""
    paths = get_project_summary_paths(project_path)
    tables_dir = paths.tables_dir

    catalog: set[tuple[str, str]] = set()

    if tables_dir is not None and tables_dir.exists():
        for tmdl_file in tables_dir.glob("*.tmdl"):
            table_name = tmdl_file.stem
            text = tmdl_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                col_match = _COLUMN_RE.match(line)
                if col_match:
                    prop = _strip_quotes(col_match.group("name"))
                    catalog.add((table_name, prop))
                    continue
                meas_match = _MEASURE_RE.match(line)
                if meas_match:
                    prop = _strip_quotes(meas_match.group("name"))
                    catalog.add((table_name, prop))

    model_dir = paths.model_dir
    model_bim = model_dir / "model.bim" if model_dir is not None else None
    if model_bim is not None and model_bim.exists():
        payload = _read_json(model_bim)
        for table in payload.get("model", {}).get("tables", []):
            table_name = table.get("name")
            if not isinstance(table_name, str):
                continue
            for column in table.get("columns", []):
                column_name = column.get("name")
                if isinstance(column_name, str):
                    catalog.add((table_name, column_name))
            for measure in table.get("measures", []):
                measure_name = measure.get("name")
                if isinstance(measure_name, str):
                    catalog.add((table_name, measure_name))

    return catalog


def _iter_visual_files(project_path: str):
    """Yield all visual.json paths under the report pages directory."""
    paths = get_project_summary_paths(project_path)
    pages_dir = paths.pages_dir
    if pages_dir is None or not pages_dir.exists():
        return
    for visual_path in pages_dir.rglob("visual.json"):
        if any(part.startswith(".") for part in visual_path.relative_to(pages_dir).parts):
            continue
        yield visual_path


def validate_reachability(project_path: str) -> ValidationReport:
    """Rule 6: every visual binding must resolve to a real model entity/property."""
    issues: list[ValidationIssue] = []

    catalog = _build_model_catalog(project_path)

    paths = get_project_summary_paths(project_path)
    if paths.pages_dir is None or not paths.pages_dir.exists():
        issues.append(
            ValidationIssue(
                severity="warning",
                code="REACH_NO_PAGES_DIR",
                message="Report pages directory not found; reachability check skipped.",
                path=project_path,
                pointer=None,
            )
        )
        return ValidationReport(ok=True, issues=issues)

    for visual_path in _iter_visual_files(project_path):
        try:
            visual_data = _read_json(visual_path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="REACH_PARSE_ERROR",
                    message=f"Could not parse visual file: {exc}",
                    path=str(visual_path),
                    pointer=None,
                )
            )
            continue

        bindings = _extract_query_state_bindings(visual_data)
        for binding in bindings:
            entity = binding["entity"]
            prop = binding["property"]
            if (entity, prop) not in catalog:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="REACH_UNRESOLVED_BINDING",
                        message=(
                            f"Visual binding '{entity}.{prop}' does not resolve to any "
                            f"table column or measure in the semantic model."
                        ),
                        path=str(visual_path),
                        pointer=binding.get("query_ref"),
                    )
                )

    has_errors = any(i.severity == "error" for i in issues)
    return ValidationReport(ok=not has_errors, issues=issues)

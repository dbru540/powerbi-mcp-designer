"""TMDL structural validation rules.

Rules implemented:
  TMDL_ORPHAN_REF  — relationship endpoints / model refs reference missing tables or columns
  TMDL_DUPLICATE   — duplicate measure / column / relationship names
  TMDL_BAD_NAME    — empty names or control characters; warn on DAX reserved words
  TMDL_COHERENCE   — cross-file consistency (model.tmdl ref table, role tablePermission)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.model.read import _strip_quotes
from powerbi_mcp.validation.report import ValidationIssue, ValidationReport

# ---------------------------------------------------------------------------
# DAX reserved words that warrant a warning when used as object names
# ---------------------------------------------------------------------------
_DAX_RESERVED = frozenset({
    "DEFINE", "EVALUATE", "ORDER", "BY", "ASC", "DESC", "VAR", "RETURN",
    "TABLE", "COLUMN", "MEASURE", "NOT", "AND", "OR", "TRUE", "FALSE",
    "IN", "DATATABLE",
})

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------
_RELATIONSHIP_HEADER_RE = re.compile(r"^relationship\s+(.+)$")
_FROM_COLUMN_RE = re.compile(r"^\s+fromColumn:\s+(.+)$")
_TO_COLUMN_RE = re.compile(r"^\s+toColumn:\s+(.+)$")
_COLUMN_HEADER_RE = re.compile(r"^\tcolumn\s+(.+)$")
_REF_TABLE_RE = re.compile(r"^ref table\s+(.+)$", re.MULTILINE)
_TABLE_PERMISSION_RE = re.compile(r"^\s+tablePermission\s+([^\s=]+)", re.MULTILINE)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_field_ref(value: str) -> tuple[str, str]:
    """Split ``Table.Column`` or ``'Table'.Column`` into (table, column)."""
    value = value.strip()
    # Handle quoted table names: 'Table Name'.Column or 'Table Name'.'Column'
    m = re.match(r"^('(?:[^']+)'|[^.]+)\.(.+)$", value)
    if m:
        return _strip_quotes(m.group(1)), _strip_quotes(m.group(2))
    return value, ""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _issue(
    severity: str,
    code: str,
    message: str,
    path: Path | str,
    pointer: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
        path=str(path),
        pointer=pointer,
    )


def _error(code: str, message: str, path: Path | str, pointer: str | None = None) -> ValidationIssue:
    return _issue("error", code, message, path, pointer)


def _warning(code: str, message: str, path: Path | str, pointer: str | None = None) -> ValidationIssue:
    return _issue("warning", code, message, path, pointer)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _get_dirs(project_path: str) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    """Return (definition_dir, tables_dir, roles_dir, relationships_path)."""
    paths = get_project_summary_paths(project_path)
    model_dir = paths.model_dir
    if model_dir is None:
        return None, None, None, None
    definition_dir = model_dir / "definition"
    tables_dir = definition_dir / "tables"
    roles_dir = definition_dir / "roles"
    relationships_path = definition_dir / "relationships.tmdl"
    return (
        definition_dir,
        tables_dir if tables_dir.exists() else None,
        roles_dir if roles_dir.exists() else None,
        relationships_path if relationships_path.exists() else None,
    )


def _on_disk_table_names(tables_dir: Path) -> frozenset[str]:
    return frozenset(p.stem for p in tables_dir.glob("*.tmdl"))



# ---------------------------------------------------------------------------
# Rule 1 — Reference integrity (TMDL_ORPHAN_REF)
# ---------------------------------------------------------------------------

def _check_orphan_refs(
    tables_dir: Path | None,
    relationships_path: Path | None,
    definition_dir: Path | None,
) -> Iterable[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if tables_dir is None:
        return issues

    table_names = _on_disk_table_names(tables_dir)

    # -- relationships.tmdl --
    if relationships_path is not None:
        text = _read_text(relationships_path)
        lines = text.splitlines()
        current_rel: str | None = None

        for line in lines:
            hm = _RELATIONSHIP_HEADER_RE.match(line)
            if hm:
                current_rel = _strip_quotes(hm.group(1).strip())
                continue

            for col_re, label in ((_FROM_COLUMN_RE, "fromColumn"), (_TO_COLUMN_RE, "toColumn")):
                cm = col_re.match(line)
                if cm:
                    table_name, col_name = _parse_field_ref(cm.group(1))
                    if table_name and table_name not in table_names:
                        issues.append(_error(
                            "TMDL_ORPHAN_REF",
                            f"Relationship '{current_rel}': {label} references unknown table '{table_name}'",
                            relationships_path,
                            pointer=f"relationship/{current_rel}/{label}",
                        ))

    # -- model.tmdl ref table entries --
    if definition_dir is not None:
        model_path = definition_dir / "model.tmdl"
        if model_path.exists():
            model_text = _read_text(model_path)
            for m in _REF_TABLE_RE.finditer(model_text):
                ref_name = _strip_quotes(m.group(1).strip())
                if ref_name not in table_names:
                    issues.append(_error(
                        "TMDL_ORPHAN_REF",
                        f"model.tmdl: 'ref table {ref_name}' references a table with no matching .tmdl file",
                        model_path,
                        pointer=f"ref/table/{ref_name}",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Rule 2 — Uniqueness (TMDL_DUPLICATE)
# ---------------------------------------------------------------------------

def _check_duplicates(
    tables_dir: Path | None,
    relationships_path: Path | None,
) -> Iterable[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if tables_dir is not None:
        for table_path in sorted(tables_dir.glob("*.tmdl")):
            table_name = table_path.stem
            measures_seen: set[str] = set()
            columns_seen: set[str] = set()

            for line in _read_text(table_path).splitlines():
                if line.startswith("\tmeasure ") and "=" in line:
                    name_part = line[len("\tmeasure "):].split("=", 1)[0].strip()
                    name = _strip_quotes(name_part)
                    if name in measures_seen:
                        issues.append(_error(
                            "TMDL_DUPLICATE",
                            f"Table '{table_name}': duplicate measure name '{name}'",
                            table_path,
                            pointer=f"table/{table_name}/measure/{name}",
                        ))
                    else:
                        measures_seen.add(name)

                cm = _COLUMN_HEADER_RE.match(line)
                if cm:
                    name = _strip_quotes(cm.group(1).strip())
                    if name in columns_seen:
                        issues.append(_error(
                            "TMDL_DUPLICATE",
                            f"Table '{table_name}': duplicate column name '{name}'",
                            table_path,
                            pointer=f"table/{table_name}/column/{name}",
                        ))
                    else:
                        columns_seen.add(name)

    # -- duplicate relationship names --
    if relationships_path is not None:
        rel_names_seen: set[str] = set()
        for line in _read_text(relationships_path).splitlines():
            hm = _RELATIONSHIP_HEADER_RE.match(line)
            if hm:
                name = _strip_quotes(hm.group(1).strip())
                if name in rel_names_seen:
                    issues.append(_error(
                        "TMDL_DUPLICATE",
                        f"Duplicate relationship name '{name}'",
                        relationships_path,
                        pointer=f"relationship/{name}",
                    ))
                else:
                    rel_names_seen.add(name)

    return issues


# ---------------------------------------------------------------------------
# Rule 4 — Naming (TMDL_BAD_NAME)
# ---------------------------------------------------------------------------

def _check_name(name: str, kind: str, context: str, path: Path) -> Iterable[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not name:
        issues.append(_error(
            "TMDL_BAD_NAME",
            f"{context}: {kind} has an empty name",
            path,
            pointer=f"{context}/{kind}/<empty>",
        ))
        return issues
    for ch, label in (("\t", "tab"), ("\n", "newline"), ("\r", "carriage-return")):
        if ch in name:
            issues.append(_error(
                "TMDL_BAD_NAME",
                f"{context}: {kind} name contains {label} character: {name!r}",
                path,
                pointer=f"{context}/{kind}/{name}",
            ))
    if name.upper() in _DAX_RESERVED:
        issues.append(_warning(
            "TMDL_BAD_NAME",
            f"{context}: {kind} name '{name}' is a DAX reserved word",
            path,
            pointer=f"{context}/{kind}/{name}",
        ))
    return issues


def _check_naming(tables_dir: Path | None) -> Iterable[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if tables_dir is None:
        return issues

    for table_path in sorted(tables_dir.glob("*.tmdl")):
        table_name = table_path.stem
        for line in _read_text(table_path).splitlines():
            if line.startswith("\tmeasure ") and "=" in line:
                name_part = line[len("\tmeasure "):].split("=", 1)[0].strip()
                name = _strip_quotes(name_part)
                issues.extend(_check_name(name, "measure", f"table/{table_name}", table_path))

            cm = _COLUMN_HEADER_RE.match(line)
            if cm:
                name = _strip_quotes(cm.group(1).strip())
                issues.extend(_check_name(name, "column", f"table/{table_name}", table_path))

    return issues


# ---------------------------------------------------------------------------
# Rule 5 — Cross-file coherence (TMDL_COHERENCE)
# ---------------------------------------------------------------------------

def _check_coherence(
    tables_dir: Path | None,
    roles_dir: Path | None,
    definition_dir: Path | None,
) -> Iterable[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if tables_dir is None:
        return issues

    table_names = _on_disk_table_names(tables_dir)

    # -- role files: tablePermission references --
    if roles_dir is not None:
        for role_path in sorted(roles_dir.glob("*.tmdl")):
            role_text = _read_text(role_path)
            for m in _TABLE_PERMISSION_RE.finditer(role_text):
                referenced_table = _strip_quotes(m.group(1).strip())
                if referenced_table and referenced_table not in table_names:
                    issues.append(_error(
                        "TMDL_COHERENCE",
                        f"Role file '{role_path.name}': tablePermission references unknown table '{referenced_table}'",
                        role_path,
                        pointer=f"role/{role_path.stem}/tablePermission/{referenced_table}",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_tmdl(project_path: str) -> ValidationReport:
    """Run all TMDL structural validation rules and return a consolidated report."""
    definition_dir, tables_dir, roles_dir, relationships_path = _get_dirs(project_path)

    issues: list[ValidationIssue] = []
    issues.extend(_check_orphan_refs(tables_dir, relationships_path, definition_dir))
    issues.extend(_check_duplicates(tables_dir, relationships_path))
    issues.extend(_check_naming(tables_dir))
    issues.extend(_check_coherence(tables_dir, roles_dir, definition_dir))

    has_errors = any(i.severity == "error" for i in issues)
    return ValidationReport(ok=not has_errors, issues=issues)

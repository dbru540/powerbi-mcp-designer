from __future__ import annotations

from pathlib import Path

from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.validation.pbir import validate_pbir_file, validate_pbir_payload
from powerbi_mcp.validation.reachability import validate_reachability
from powerbi_mcp.validation.report import ValidationReport
from powerbi_mcp.validation.tmdl import validate_tmdl


def validate_project(project_path: str) -> ValidationReport:
    """Run PBIR + TMDL + reachability validation, merged into one report."""
    reports: list[ValidationReport] = []
    reports.append(validate_report(project_path))
    reports.append(validate_tmdl(project_path))
    reports.append(validate_reachability(project_path))
    return ValidationReport.merge(reports)


def validate_report(project_path: str) -> ValidationReport:
    """Run PBIR validation only (all JSON files under the .Report directory)."""
    paths = get_project_summary_paths(project_path)
    report_dir = paths.report_dir
    if report_dir is None or not report_dir.exists():
        return ValidationReport.ok_report()

    reports: list[ValidationReport] = []
    for json_file in report_dir.rglob("*.json"):
        if any(part.startswith(".") for part in json_file.relative_to(report_dir).parts):
            continue
        reports.append(validate_pbir_file(str(json_file)))

    if not reports:
        return ValidationReport.ok_report()
    return ValidationReport.merge(reports)


def validate_model(project_path: str) -> ValidationReport:
    """Run TMDL validation only."""
    return validate_tmdl(project_path)


def pre_validate_payload(payload: dict, file_path: str) -> ValidationReport:
    """Validate a proposed JSON payload against PBIR schema before writing."""
    return validate_pbir_payload(payload, file_path)


def post_validate_paths(project_path: str, touched_paths: list[str]) -> ValidationReport:
    """Re-validate touched files after a write.

    For JSON files, runs PBIR validation. If any .tmdl files were touched,
    also runs validate_tmdl once. Merges all results.
    """
    reports: list[ValidationReport] = []
    has_tmdl = False

    for path_str in touched_paths:
        path = Path(path_str)
        if path.suffix.lower() == ".json":
            reports.append(validate_pbir_file(path_str))
        elif path.suffix.lower() == ".tmdl":
            has_tmdl = True

    if has_tmdl:
        reports.append(validate_tmdl(project_path))

    if not reports:
        return ValidationReport.ok_report()
    return ValidationReport.merge(reports)

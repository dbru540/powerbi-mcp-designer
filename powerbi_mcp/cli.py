from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import NamedTuple

from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.validation.engine import validate_project


class CheckResult(NamedTuple):
    status: str
    name: str
    detail: str


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _find_powerbi_desktop() -> Path | None:
    env_path = os.environ.get("POWERBI_DESKTOP_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    executable = shutil.which("PBIDesktop.exe") or shutil.which("PBIDesktop")
    if executable:
        return Path(executable)

    if platform.system() == "Windows":
        default_path = Path("C:/Program Files/Microsoft Power BI Desktop/bin/PBIDesktop.exe")
        if default_path.exists():
            return default_path

    return None


def _dependency_checks() -> list[CheckResult]:
    checks: list[CheckResult] = []
    for module_name in ("mcp", "jsonschema", "pydantic"):
        if _module_available(module_name):
            checks.append(CheckResult("ok", f"dependency:{module_name}", "importable"))
        else:
            checks.append(CheckResult("fail", f"dependency:{module_name}", "not importable"))
    return checks


def _project_checks(project_path: Path, validate: bool) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if not project_path.exists():
        return [CheckResult("fail", "project", f"path does not exist: {project_path}")]

    paths = get_project_summary_paths(project_path)
    checks.append(CheckResult("ok", "project", str(paths.project_dir)))

    required_paths = (
        ("pbip", paths.pbip_file),
        ("report_dir", paths.report_dir),
        ("model_dir", paths.model_dir),
        ("pages_dir", paths.pages_dir),
        ("tables_dir", paths.tables_dir),
    )
    for name, path in required_paths:
        if path is not None and path.exists():
            checks.append(CheckResult("ok", name, str(path)))
        else:
            checks.append(CheckResult("fail", name, "not found"))

    if validate:
        report = validate_project(str(project_path))
        errors = report.errors()
        warnings = report.warnings()
        if errors:
            checks.append(CheckResult("fail", "validation", f"{len(errors)} error(s), {len(warnings)} warning(s)"))
        else:
            checks.append(CheckResult("ok", "validation", f"0 error(s), {len(warnings)} warning(s)"))

    return checks


def _print_check(result: CheckResult) -> None:
    label = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[result.status]
    print(f"[{label}] {result.name}: {result.detail}")


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="powerbi-mcp-doctor",
        description="Check the local Power BI MCP server installation.",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Optional PBIP project directory to inspect.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip full PBIR/TMDL validation for --project.",
    )
    args = parser.parse_args(argv)

    checks: list[CheckResult] = []
    python_ok = sys.version_info >= (3, 10)
    checks.append(
        CheckResult(
            "ok" if python_ok else "fail",
            "python",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    checks.extend(_dependency_checks())

    desktop_path = _find_powerbi_desktop()
    if desktop_path is None:
        checks.append(
            CheckResult(
                "warn",
                "powerbi_desktop",
                "not found; file-first PBIP tools still work, desktop screenshot automation will be unavailable",
            )
        )
    else:
        checks.append(CheckResult("ok", "powerbi_desktop", str(desktop_path)))

    if args.project is not None:
        checks.extend(_project_checks(args.project, validate=not args.no_validate))

    for check in checks:
        _print_check(check)

    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(doctor_main())

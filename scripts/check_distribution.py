from __future__ import annotations

import argparse
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path


REQUIRED_PROJECT_FILES = (
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "README_INSTALL.md",
    "RELEASE.md",
    "pyproject.toml",
    ".mcp.json.example",
    ".github/workflows/ci.yml",
    ".github/workflows/publish.yml",
)

REQUIRED_SCRIPTS = {
    "powerbi-mcp": "powerbi_mcp.server:main",
    "powerbi-mcp-server": "powerbi_mcp.server:main",
    "powerbi-mcp-server-designer": "powerbi_mcp.server:main",
    "powerbi-mcp-doctor": "powerbi_mcp.cli:doctor_main",
}

REQUIRED_WHEEL_PATHS = (
    "powerbi_mcp/server.py",
    "powerbi_mcp/cli.py",
    "powerbi_mcp/validation/schemas/INDEX.json",
)

REQUIRED_SDIST_SUFFIXES = (
    "README_INSTALL.md",
    "RELEASE.md",
    ".mcp.json.example",
    ".github/workflows/ci.yml",
    ".github/workflows/publish.yml",
)


@dataclass(frozen=True)
class CheckResult:
    messages: list[str]

    @property
    def ok(self) -> bool:
        return not self.messages


def _ok() -> CheckResult:
    return CheckResult([])


def check_project_files(repo_root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_PROJECT_FILES if not (repo_root / path).exists()]
    return CheckResult([f"missing required distribution file: {path}" for path in missing])


def check_pyproject_metadata(pyproject_path: Path) -> CheckResult:
    messages: list[str] = []
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    scripts = project.get("scripts", {})

    if project.get("name") != "powerbi-mcp-server-designer":
        messages.append("project.name must be powerbi-mcp-server-designer")
    if not project.get("version"):
        messages.append("project.version is required")
    if project.get("license") != "MIT":
        messages.append("project.license must use SPDX string MIT")
    if project.get("readme") != "README.md":
        messages.append("project.readme must be README.md")

    for script_name, target in REQUIRED_SCRIPTS.items():
        if scripts.get(script_name) != target:
            messages.append(f"project.scripts.{script_name} must be {target}")

    return CheckResult(messages)


def _find_single(dist_dir: Path, pattern: str) -> Path | None:
    matches = sorted(dist_dir.glob(pattern))
    return matches[0] if len(matches) == 1 else None


def _check_wheel(wheel_path: Path) -> list[str]:
    messages: list[str] = []
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        for required_path in REQUIRED_WHEEL_PATHS:
            if required_path not in names:
                messages.append(f"wheel missing required path: {required_path}")
        if any(name.startswith("powerbi_mcp/tests/") for name in names):
            messages.append("wheel must not include powerbi_mcp/tests")
        entry_points = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if not entry_points:
            messages.append("wheel missing entry_points.txt")
    return messages


def _check_sdist(sdist_path: Path) -> list[str]:
    messages: list[str] = []
    with tarfile.open(sdist_path, "r:gz") as sdist:
        names = set(sdist.getnames())
    for required_suffix in REQUIRED_SDIST_SUFFIXES:
        if not any(name.endswith(required_suffix) for name in names):
            messages.append(f"sdist missing required path ending: {required_suffix}")
    return messages


def check_dist_artifacts(dist_dir: Path) -> CheckResult:
    messages: list[str] = []
    wheel_path = _find_single(dist_dir, "*.whl")
    sdist_path = _find_single(dist_dir, "*.tar.gz")

    if wheel_path is None:
        messages.append("dist must contain exactly one wheel")
    else:
        messages.extend(_check_wheel(wheel_path))

    if sdist_path is None:
        messages.append("dist must contain exactly one source distribution")
    else:
        try:
            messages.extend(_check_sdist(sdist_path))
        except tarfile.TarError:
            messages.append("source distribution is not a readable tar.gz archive")

    return CheckResult(messages)


def run_checks(repo_root: Path, dist_dir: Path | None = None) -> CheckResult:
    messages: list[str] = []
    for result in (
        check_project_files(repo_root),
        check_pyproject_metadata(repo_root / "pyproject.toml"),
    ):
        messages.extend(result.messages)
    if dist_dir is not None:
        messages.extend(check_dist_artifacts(dist_dir).messages)
    return CheckResult(messages)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_distribution.py",
        description="Validate package distribution readiness for Power BI MCP Server.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        help="Optional dist directory containing a built wheel and sdist.",
    )
    args = parser.parse_args(argv)

    result = run_checks(args.repo_root, args.dist_dir)
    if result.ok:
        print("Distribution checks passed.")
        return 0

    for message in result.messages:
        print(f"FAIL: {message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

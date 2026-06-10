from __future__ import annotations

import json
import hashlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from powerbi_mcp.report.read import report_list_pages
from powerbi_mcp.validation.engine import validate_project
from powerbi_mcp.visual_ai.desktop_evidence import summarize_desktop_evidence
from powerbi_mcp.visual_ai.readiness import report_design_readiness_check
from powerbi_mcp.visual_ai.screenshot_quality import analyze_screenshot_readiness
from powerbi_mcp.visual_ai.studio import report_design_studio_plan
from powerbi_mcp.visual_ai.windows_capture import capture_powerbi_desktop_screenshot, navigate_powerbi_report_page


DEFAULT_VISUAL_QA_OUTPUT_DIR = Path("C:/_pbimcp_visual_qa")
DesktopLauncher = Callable[[str, str], dict[str, Any]]
ScreenshotBackend = Callable[[int | None, dict[str, Any], Path, float], dict[str, Any]]
PageNavigator = Callable[[int | None, dict[str, Any], dict[str, Any], int, float], dict[str, Any]]
ScreenshotReadinessAnalyzer = Callable[[str | None], dict[str, Any]]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


def _resolve_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def discover_pbip_projects(test_root: str) -> list[dict[str, Any]]:
    """Find PBIP projects under a test root."""
    root = Path(test_root)
    if not root.exists():
        return []

    projects: list[dict[str, Any]] = []
    seen_project_paths: set[Path] = set()
    for pbip_file in sorted(root.rglob("*.pbip")):
        if not pbip_file.is_file():
            continue
        project_path = pbip_file.parent.resolve(strict=False)
        if project_path in seen_project_paths:
            continue
        seen_project_paths.add(project_path)
        projects.append(
            {
                "name": pbip_file.stem,
                "project_path": _resolve_path(project_path),
                "pbip_file": _resolve_path(pbip_file),
            }
        )
    return projects


def _desktop_probe(pbidesktop_path: str | None, launch_desktop: bool) -> dict[str, Any]:
    probe = {
        "launch_requested": launch_desktop,
        "path": pbidesktop_path,
        "path_ok": None,
        "launch_attempted": False,
        "pids": [],
        "error": None,
    }
    if not launch_desktop:
        if pbidesktop_path:
            probe["path_ok"] = Path(pbidesktop_path).exists()
        return probe

    if not pbidesktop_path:
        probe["path_ok"] = False
        probe["error"] = "Power BI Desktop path is required when launch_desktop is true."
        return probe

    path_ok = Path(pbidesktop_path).exists()
    probe["path_ok"] = path_ok
    if not path_ok:
        probe["error"] = f"Power BI Desktop executable not found: {pbidesktop_path}"
    return probe


def _launch_desktop(pbidesktop_path: str, pbip_file: str) -> dict[str, Any]:
    launch = {
        "attempted": True,
        "pid": None,
        "screenshot": {
            "attempted": False,
            "path": None,
            "window_title": None,
            "error": None,
        },
        "page_screenshots": [],
        "render_readiness": {"attempted": False, "status": "not-requested"},
        "render_attempts": [],
        "render_retry": {"requested": False, "status": "not-requested", "attempt_count": 0},
        "visual_comparison": {"attempted": False, "status": "not-requested"},
        "error": None,
    }
    try:
        process = subprocess.Popen(  # noqa: S603 - user-supplied local executable path is intentional here.
            [pbidesktop_path, pbip_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        launch["error"] = str(exc)
        return launch

    launch["pid"] = process.pid
    return launch


def _not_attempted_desktop_launch() -> dict[str, Any]:
    return {
        "attempted": False,
        "pid": None,
        "screenshot": {
            "attempted": False,
            "path": None,
            "window_title": None,
            "error": None,
        },
        "page_screenshots": [],
        "render_readiness": {"attempted": False, "status": "not-requested"},
        "render_attempts": [],
        "render_retry": {"requested": False, "status": "not-requested", "attempt_count": 0},
        "visual_comparison": {"attempted": False, "status": "not-requested"},
        "error": None,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_screenshot_to_baseline(actual_path: str | None, baseline_dir: str | None) -> dict[str, Any]:
    if not baseline_dir:
        return {"attempted": False, "status": "not-requested"}

    comparison = {
        "attempted": True,
        "status": "missing-actual",
        "actual_path": actual_path,
        "baseline_path": None,
        "actual_sha256": None,
        "baseline_sha256": None,
        "actual_size_bytes": None,
        "baseline_size_bytes": None,
        "error": None,
    }
    if not actual_path:
        return comparison

    actual = Path(actual_path)
    if not actual.exists():
        comparison["error"] = f"Actual screenshot not found: {actual_path}"
        return comparison

    baseline = Path(baseline_dir) / actual.name
    comparison["baseline_path"] = str(baseline.resolve(strict=False))
    comparison["actual_sha256"] = _sha256_file(actual)
    comparison["actual_size_bytes"] = actual.stat().st_size
    if not baseline.exists():
        comparison["status"] = "missing-baseline"
        return comparison

    comparison["baseline_sha256"] = _sha256_file(baseline)
    comparison["baseline_size_bytes"] = baseline.stat().st_size
    comparison["status"] = (
        "matched" if comparison["actual_sha256"] == comparison["baseline_sha256"] else "different"
    )
    return comparison


def _safe_capture_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "-" for char in value)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "capture"


def _report_pages(project_path: str, limit: int | None) -> list[dict[str, Any]]:
    pages_result = report_list_pages(project_path)
    if "error" in pages_result:
        return []
    pages = list(pages_result.get("pages", []))
    if limit is not None:
        return pages[: max(limit, 0)]
    return pages


def _capture_single_desktop_screenshot(
    project: dict[str, Any],
    pid: int | None,
    output_path: Path,
    desktop_wait_seconds: float,
    baseline_dir: str | None,
    screenshot_backend: ScreenshotBackend,
    screenshot_readiness_analyzer: ScreenshotReadinessAnalyzer,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    screenshot = screenshot_backend(pid, project, output_path, desktop_wait_seconds)
    readiness = screenshot_readiness_analyzer(screenshot.get("path"))
    if screenshot.get("path"):
        comparison = compare_screenshot_to_baseline(screenshot["path"], baseline_dir)
    else:
        comparison = compare_screenshot_to_baseline(None, baseline_dir)
    return screenshot, comparison, readiness, bool(screenshot.get("error"))


def _capture_desktop_screenshot_until_ready(
    project: dict[str, Any],
    pid: int | None,
    output_path: Path,
    desktop_wait_seconds: float,
    baseline_dir: str | None,
    screenshot_backend: ScreenshotBackend,
    screenshot_readiness_analyzer: ScreenshotReadinessAnalyzer,
    render_readiness_retry_seconds: float,
    render_readiness_retry_interval_seconds: float,
    clock: Clock,
    sleeper: Sleeper,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], bool]:
    retry_requested = render_readiness_retry_seconds > 0
    retry_interval = max(render_readiness_retry_interval_seconds, 0.1)
    deadline = clock() + max(render_readiness_retry_seconds, 0)
    attempts: list[dict[str, Any]] = []
    retry = {
        "requested": retry_requested,
        "timeout_seconds": render_readiness_retry_seconds,
        "interval_seconds": render_readiness_retry_interval_seconds,
        "attempt_count": 0,
        "status": "not-requested",
    }

    while True:
        screenshot, comparison, readiness, screenshot_failed = _capture_single_desktop_screenshot(
            project,
            pid,
            output_path,
            desktop_wait_seconds,
            baseline_dir,
            screenshot_backend,
            screenshot_readiness_analyzer,
        )
        attempts.append(
            {
                "attempt": len(attempts) + 1,
                "screenshot": screenshot,
                "render_readiness": readiness,
                "visual_comparison": comparison,
            }
        )
        retry["attempt_count"] = len(attempts)
        if screenshot_failed:
            retry["status"] = "capture-error"
            return screenshot, comparison, readiness, attempts, retry, True
        if readiness.get("status") == "ready":
            retry["status"] = "ready" if retry_requested else "not-needed"
            return screenshot, comparison, readiness, attempts, retry, False
        if not retry_requested:
            return screenshot, comparison, readiness, attempts, retry, False

        remaining_seconds = deadline - clock()
        if remaining_seconds <= 0:
            retry["status"] = "timeout"
            return screenshot, comparison, readiness, attempts, retry, False
        sleeper(min(retry_interval, remaining_seconds))


def _capture_all_report_pages(
    project: dict[str, Any],
    pid: int | None,
    output_path: Path,
    desktop_wait_seconds: float,
    baseline_dir: str | None,
    screenshot_page_limit: int | None,
    page_navigation_delay_seconds: float,
    render_readiness_retry_seconds: float,
    render_readiness_retry_interval_seconds: float,
    screenshot_backend: ScreenshotBackend,
    page_navigator: PageNavigator,
    screenshot_readiness_analyzer: ScreenshotReadinessAnalyzer,
    clock: Clock,
    sleeper: Sleeper,
) -> tuple[list[dict[str, Any]], bool]:
    page_captures: list[dict[str, Any]] = []
    blocked = False
    for page_index, page in enumerate(_report_pages(project["project_path"], screenshot_page_limit)):
        navigation = page_navigator(pid, project, page, page_index, page_navigation_delay_seconds)
        capture_project = {
            **project,
            "active_page": page,
            "capture_name": _safe_capture_name(f"{project['name']}-{page_index + 1:02d}-{page['id']}"),
        }
        screenshot, comparison, readiness, attempts, retry, screenshot_failed = _capture_desktop_screenshot_until_ready(
            capture_project,
            pid,
            output_path,
            desktop_wait_seconds,
            baseline_dir,
            screenshot_backend,
            screenshot_readiness_analyzer,
            render_readiness_retry_seconds,
            render_readiness_retry_interval_seconds,
            clock,
            sleeper,
        )
        page_capture = {
            "page_index": page_index,
            "page_id": page.get("id"),
            "page_name": page.get("displayName"),
            "navigation": navigation,
            "screenshot": screenshot,
            "render_readiness": readiness,
            "render_attempts": attempts,
            "render_retry": retry,
            "visual_comparison": comparison,
        }
        page_captures.append(page_capture)
        if navigation.get("error") or screenshot_failed:
            blocked = True
            break
    if not page_captures:
        blocked = True
    return page_captures, blocked


def _run_project_visual_qa(
    project: dict[str, Any],
    audience: str,
    intent: str,
    subject: str | None,
    page_limit: int,
    desktop: dict[str, Any],
    output_path: Path,
    capture_screenshot: bool,
    capture_all_pages: bool,
    desktop_wait_seconds: float,
    screenshot_page_limit: int | None,
    page_navigation_delay_seconds: float,
    render_readiness_retry_seconds: float,
    render_readiness_retry_interval_seconds: float,
    baseline_dir: str | None,
    desktop_launcher: DesktopLauncher,
    screenshot_backend: ScreenshotBackend,
    page_navigator: PageNavigator,
    screenshot_readiness_analyzer: ScreenshotReadinessAnalyzer,
    clock: Clock,
    sleeper: Sleeper,
) -> dict[str, Any]:
    project_path = project["project_path"]
    validation = validate_project(project_path).to_dict()
    readiness = report_design_readiness_check(
        project_path,
        audience=audience,
        intent=intent,
        subject=subject,
        page_limit=page_limit,
    )
    studio = report_design_studio_plan(
        project_path,
        audience=audience,
        intent=intent,
        subject=subject,
        page_limit=page_limit,
    )
    status = "passed" if validation["ok"] and readiness.get("status") == "mvp-ready" else "failed"
    desktop_launch = _not_attempted_desktop_launch()
    if desktop["launch_requested"] and desktop["path_ok"]:
        desktop_launch = desktop_launcher(str(desktop["path"]), str(project["pbip_file"]))
        desktop["launch_attempted"] = True
        if desktop_launch["pid"] is not None:
            desktop["pids"].append(desktop_launch["pid"])
        if desktop_launch["error"]:
            status = "blocked"
        elif capture_screenshot:
            if capture_all_pages:
                page_screenshots, page_capture_blocked = _capture_all_report_pages(
                    project,
                    desktop_launch["pid"],
                    output_path,
                    desktop_wait_seconds,
                    baseline_dir,
                    screenshot_page_limit,
                    page_navigation_delay_seconds,
                    render_readiness_retry_seconds,
                    render_readiness_retry_interval_seconds,
                    screenshot_backend,
                    page_navigator,
                    screenshot_readiness_analyzer,
                    clock,
                    sleeper,
                )
                desktop_launch["page_screenshots"] = page_screenshots
                if page_screenshots:
                    desktop_launch["screenshot"] = page_screenshots[0]["screenshot"]
                    desktop_launch["render_readiness"] = page_screenshots[0]["render_readiness"]
                    desktop_launch["render_attempts"] = page_screenshots[0]["render_attempts"]
                    desktop_launch["render_retry"] = page_screenshots[0]["render_retry"]
                    desktop_launch["visual_comparison"] = page_screenshots[0]["visual_comparison"]
                if page_capture_blocked:
                    status = "blocked"
            else:
                screenshot, comparison, readiness, attempts, retry, screenshot_failed = (
                    _capture_desktop_screenshot_until_ready(
                        project,
                        desktop_launch["pid"],
                        output_path,
                        desktop_wait_seconds,
                        baseline_dir,
                        screenshot_backend,
                        screenshot_readiness_analyzer,
                        render_readiness_retry_seconds,
                        render_readiness_retry_interval_seconds,
                        clock,
                        sleeper,
                    )
                )
                desktop_launch["screenshot"] = screenshot
                desktop_launch["render_readiness"] = readiness
                desktop_launch["render_attempts"] = attempts
                desktop_launch["render_retry"] = retry
                desktop_launch["visual_comparison"] = comparison
                if screenshot_failed:
                    status = "blocked"

    return {
        **project,
        "status": status,
        "validation": validation,
        "readiness": readiness,
        "studio": studio,
        "desktop_launch": desktop_launch,
    }


def _overall_status(project_results: list[dict[str, Any]], desktop: dict[str, Any]) -> str:
    if not project_results:
        return "blocked"
    if desktop["launch_requested"] and not desktop["path_ok"]:
        return "blocked"
    if any(project["status"] == "blocked" for project in project_results):
        return "blocked"
    if any(project["status"] == "failed" for project in project_results):
        return "failed"
    return "passed"


def _attach_visual_evidence_studio_plans(
    result: dict[str, Any],
    report_file: Path,
    audience: str,
    intent: str,
    subject: str | None,
    page_limit: int,
) -> None:
    for project in result["projects"]:
        project["visual_evidence_studio"] = report_design_studio_plan(
            project["project_path"],
            audience=audience,
            intent=intent,
            subject=subject,
            page_limit=page_limit,
            visual_qa_report_file=str(report_file.resolve(strict=False)),
        )


def run_file_first_visual_qa_loop(
    test_root: str,
    audience: str,
    intent: str,
    subject: str | None = None,
    pbidesktop_path: str | None = None,
    launch_desktop: bool = False,
    capture_screenshot: bool = False,
    capture_all_pages: bool = False,
    desktop_wait_seconds: float = 45,
    screenshot_page_limit: int | None = None,
    page_navigation_delay_seconds: float = 2,
    render_readiness_retry_seconds: float = 0,
    render_readiness_retry_interval_seconds: float = 5,
    baseline_dir: str | None = None,
    output_dir: str | None = None,
    page_limit: int = 1,
    desktop_launcher: DesktopLauncher = _launch_desktop,
    screenshot_backend: ScreenshotBackend = capture_powerbi_desktop_screenshot,
    page_navigator: PageNavigator = navigate_powerbi_report_page,
    screenshot_readiness_analyzer: ScreenshotReadinessAnalyzer = analyze_screenshot_readiness,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> dict[str, Any]:
    """Run a repeatable file-first QA loop for PBIP report-design readiness."""
    output_path = Path(output_dir) if output_dir else DEFAULT_VISUAL_QA_OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    desktop = _desktop_probe(pbidesktop_path, launch_desktop)
    desktop["capture_screenshot_requested"] = capture_screenshot
    desktop["capture_all_pages_requested"] = capture_all_pages
    desktop["wait_seconds"] = desktop_wait_seconds
    desktop["screenshot_page_limit"] = screenshot_page_limit
    desktop["page_navigation_delay_seconds"] = page_navigation_delay_seconds
    desktop["render_readiness_retry_seconds"] = render_readiness_retry_seconds
    desktop["render_readiness_retry_interval_seconds"] = render_readiness_retry_interval_seconds
    desktop["baseline_dir"] = baseline_dir
    projects = discover_pbip_projects(test_root)
    project_results = [
        _run_project_visual_qa(
            project,
            audience=audience,
            intent=intent,
            subject=subject,
            page_limit=page_limit,
            desktop=desktop,
            output_path=output_path,
            capture_screenshot=capture_screenshot,
            capture_all_pages=capture_all_pages,
            desktop_wait_seconds=desktop_wait_seconds,
            screenshot_page_limit=screenshot_page_limit,
            page_navigation_delay_seconds=page_navigation_delay_seconds,
            render_readiness_retry_seconds=render_readiness_retry_seconds,
            render_readiness_retry_interval_seconds=render_readiness_retry_interval_seconds,
            baseline_dir=baseline_dir,
            desktop_launcher=desktop_launcher,
            screenshot_backend=screenshot_backend,
            page_navigator=page_navigator,
            screenshot_readiness_analyzer=screenshot_readiness_analyzer,
            clock=clock,
            sleeper=sleeper,
        )
        for project in projects
    ]
    report_file = output_path / "visual-qa-report.json"
    result = {
        "status": _overall_status(project_results, desktop),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_root": _resolve_path(Path(test_root)),
        "audience": audience,
        "intent": intent,
        "subject": subject,
        "page_limit": page_limit,
        "mutates_files": False,
        "project_count": len(project_results),
        "desktop": desktop,
        "projects": project_results,
        "report_file": _resolve_path(report_file),
    }
    result["desktop_evidence_summary"] = summarize_desktop_evidence(result)
    report_file.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    if capture_screenshot:
        _attach_visual_evidence_studio_plans(
            result,
            report_file,
            audience=audience,
            intent=intent,
            subject=subject,
            page_limit=page_limit,
        )
        report_file.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    return result

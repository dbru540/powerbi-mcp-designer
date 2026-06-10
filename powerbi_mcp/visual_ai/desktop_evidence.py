from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_UNUSABLE_STATUSES = {"low-content", "missing-actual", "unsupported", "unknown", "not-captured"}


def _resolve_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def _status_key(status: str) -> str:
    return status.replace("-", "_")


def _recommendation_for_status(status: str, retry_status: str | None) -> str:
    if status == "ready":
        return "Use this screenshot as Desktop evidence for visual design critique."
    if status == "low-content":
        if retry_status == "timeout":
            return "Do not use this screenshot for design critique; Desktop evidence stayed blank after retry timeout."
        return "Do not use this screenshot for design critique; recapture after the report canvas finishes rendering."
    if status in {"missing-actual", "unsupported"}:
        return "Do not use this screenshot for design critique; capture evidence is missing or unreadable."
    return "Treat this page as lacking usable Desktop evidence until a ready screenshot is captured."


def _page_entry(project_name: str, capture: dict[str, Any]) -> dict[str, Any]:
    readiness = capture.get("render_readiness") or {}
    retry = capture.get("render_retry") or {}
    screenshot = capture.get("screenshot") or {}
    status = str(readiness.get("status") or "unknown")
    retry_status = retry.get("status")
    return {
        "project_name": project_name,
        "page_index": capture.get("page_index"),
        "page_id": capture.get("page_id"),
        "page_name": capture.get("page_name"),
        "evidence_status": status,
        "usable": status == "ready",
        "screenshot_path": screenshot.get("path"),
        "content_ratio": readiness.get("content_ratio"),
        "edge_ratio": readiness.get("edge_ratio"),
        "render_retry_status": retry_status,
        "render_attempt_count": retry.get("attempt_count"),
        "recommendation": _recommendation_for_status(status, retry_status),
    }


def _single_capture_entry(project: dict[str, Any]) -> dict[str, Any] | None:
    launch = project.get("desktop_launch") or {}
    screenshot = launch.get("screenshot") or {}
    readiness = launch.get("render_readiness") or {}
    if not launch.get("attempted") and not screenshot.get("attempted"):
        return None
    return {
        "page_index": None,
        "page_id": None,
        "page_name": "Desktop window",
        "screenshot": screenshot,
        "render_readiness": readiness if readiness else {"status": "not-captured"},
        "render_retry": launch.get("render_retry") or {},
    }


def _collect_pages(qa_result: dict[str, Any]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for project in qa_result.get("projects", []):
        project_name = str(project.get("name") or project.get("project_path") or "unknown-project")
        launch = project.get("desktop_launch") or {}
        captures = list(launch.get("page_screenshots") or [])
        if not captures:
            single = _single_capture_entry(project)
            if single is not None:
                captures = [single]
        pages.extend(_page_entry(project_name, capture) for capture in captures)
    return pages


def _empty_totals(project_count: int) -> dict[str, int]:
    return {
        "projects": project_count,
        "pages": 0,
        "ready": 0,
        "low_content": 0,
        "missing_actual": 0,
        "unsupported": 0,
        "not_captured": 0,
        "unknown": 0,
    }


def _overall_status(pages: list[dict[str, Any]], capture_requested: bool) -> str:
    if not capture_requested:
        return "not-requested"
    if not pages:
        return "no-evidence"
    ready_count = sum(1 for page in pages if page["evidence_status"] == "ready")
    unusable_count = sum(1 for page in pages if page["evidence_status"] in _UNUSABLE_STATUSES)
    if ready_count == len(pages):
        return "ready"
    if ready_count and unusable_count:
        return "partial"
    return "needs-render"


def _summary_recommendation(status: str) -> str:
    if status == "ready":
        return "All captured Desktop pages have usable visual evidence."
    if status == "partial":
        return "Use only ready pages for visual critique; recapture low-content or missing pages before judging layout."
    if status == "needs-render":
        return "Do not run screenshot-based design critique yet; Desktop evidence is blank, missing, or unreadable."
    if status == "not-requested":
        return "Desktop screenshot evidence was not requested."
    return "No usable Desktop evidence was found in this QA result."


def summarize_desktop_evidence(qa_result: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether QA Desktop screenshots are usable for visual design critique."""
    desktop = qa_result.get("desktop") or {}
    capture_requested = bool(desktop.get("capture_screenshot_requested"))
    project_count = len(qa_result.get("projects", []))
    pages = _collect_pages(qa_result)
    totals = _empty_totals(project_count)
    totals["pages"] = len(pages)
    for page in pages:
        key = _status_key(str(page["evidence_status"]))
        if key not in totals:
            key = "unknown"
        totals[key] += 1

    status = _overall_status(pages, capture_requested)
    usable_pages = [page for page in pages if page["usable"]]
    unusable_pages = [page for page in pages if not page["usable"]]
    return {
        "attempted": capture_requested,
        "status": status,
        "totals": totals,
        "usable_page_count": len(usable_pages),
        "unusable_page_count": len(unusable_pages),
        "pages": pages,
        "usable_pages": usable_pages,
        "unusable_pages": unusable_pages,
        "recommendation": _summary_recommendation(status),
    }


def report_design_desktop_evidence_summary(report_file: str) -> dict[str, Any]:
    """Read a visual-qa-report.json file and return a compact Desktop evidence summary."""
    path = Path(report_file)
    resolved = _resolve_path(path)
    if not path.exists():
        return {
            "attempted": True,
            "status": "blocked",
            "report_file": resolved,
            "error": f"Visual QA report file not found: {resolved}",
        }

    try:
        qa_result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "attempted": True,
            "status": "blocked",
            "report_file": resolved,
            "error": str(exc),
        }

    summary = summarize_desktop_evidence(qa_result)
    summary["report_file"] = resolved
    return summary

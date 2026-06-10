import json
from pathlib import Path
from typing import Any

from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.model.read import model_get_summary


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_pages_dir(project_path: str) -> Path | None:
    return get_project_summary_paths(project_path).pages_dir


def _iter_visible_visual_dirs(visuals_dir: Path):
    return sorted(v_dir for v_dir in visuals_dir.iterdir() if v_dir.is_dir() and not v_dir.name.startswith("."))


def _extract_visual_title(visual_data: dict[str, Any]) -> str | None:
    objects = visual_data.get("visual", {}).get("visualContainerObjects", {})
    title_obj = objects.get("title", [])
    if not title_obj:
        return None

    title_props = title_obj[0].get("properties", {})
    title_expr = title_props.get("text", {}).get("expr", {}).get("Literal", {})
    return title_expr.get("Value", "").strip("'\"") or None


def _serialize_project_paths(project_path: str) -> dict[str, Any]:
    summary = get_project_summary_paths(project_path)
    return {
        "project_path": str(summary.project_dir),
        "pbip_file": str(summary.pbip_file) if summary.pbip_file else None,
        "report_dir": str(summary.report_dir) if summary.report_dir else None,
        "model_dir": str(summary.model_dir) if summary.model_dir else None,
        "pages_dir": str(summary.pages_dir) if summary.pages_dir else None,
        "tables_dir": str(summary.tables_dir) if summary.tables_dir else None,
    }


def report_list_pages(project_path: str) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None or not pages_dir.exists():
        return {"error": f"Pages directory not found in {project_path}"}

    meta_path = pages_dir / "pages.json"
    if not meta_path.exists():
        return {"error": "pages.json not found"}

    meta = _read_json(meta_path)
    pages: list[dict[str, Any]] = []

    for page_id in meta.get("pageOrder", []):
        page_json = pages_dir / page_id / "page.json"
        if not page_json.exists():
            continue

        page_data = _read_json(page_json)
        visuals_dir = pages_dir / page_id / "visuals"
        visual_count = 0
        if visuals_dir.exists():
            visual_count = len(list(_iter_visible_visual_dirs(visuals_dir)))

        pages.append(
            {
                "id": page_id,
                "displayName": page_data.get("displayName", ""),
                "width": page_data.get("width", 1280),
                "height": page_data.get("height", 720),
                "visual_count": visual_count,
            }
        )

    return {"pages": pages, "count": len(pages)}


def report_get_page(project_path: str, page_id: str) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        return {"error": "Pages directory not found"}

    page_json = pages_dir / page_id / "page.json"
    if not page_json.exists():
        return {"error": f"Page not found: {page_id}"}

    return _read_json(page_json)


def report_list_visuals(project_path: str, page_id: str) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Visuals directory not found for page {page_id}"}

    visuals: list[dict[str, Any]] = []
    for visual_dir in _iter_visible_visual_dirs(visuals_dir):
        visual_json = visual_dir / "visual.json"
        if not visual_json.exists():
            continue

        visual_data = _read_json(visual_json)
        position = visual_data.get("position", {})
        visuals.append(
            {
                "id": visual_dir.name,
                "visualType": visual_data.get("visual", {}).get("visualType", "unknown"),
                "title": _extract_visual_title(visual_data),
                "position": {
                    "x": position.get("x", 0),
                    "y": position.get("y", 0),
                    "width": position.get("width", 0),
                    "height": position.get("height", 0),
                },
            }
        )

    return {"visuals": visuals, "count": len(visuals)}


def report_get_visual(project_path: str, page_id: str, visual_id: str) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        return {"error": "Pages directory not found"}

    visual_json = pages_dir / page_id / "visuals" / visual_id / "visual.json"
    if not visual_json.exists():
        return {"error": f"Visual not found: {visual_id}"}

    return _read_json(visual_json)


def report_get_summary(project_path: str) -> dict[str, Any]:
    path_summary = _serialize_project_paths(project_path)
    if path_summary["report_dir"] is None:
        return {"error": f"No .Report folder found in {project_path}"}

    pages_result = report_list_pages(project_path)
    if "error" in pages_result:
        return pages_result

    visual_count = 0
    for page in pages_result["pages"]:
        visuals_result = report_list_visuals(project_path, page["id"])
        if "error" in visuals_result:
            return visuals_result
        visual_count += visuals_result["count"]

    return {
        "report_dir": path_summary["report_dir"],
        "page_count": pages_result["count"],
        "visual_count": visual_count,
    }


def project_get_summary(project_path: str) -> dict[str, Any]:
    summary = _serialize_project_paths(project_path)

    report_summary = report_get_summary(project_path)
    if "error" in report_summary:
        return {**summary, **report_summary}

    model_summary = model_get_summary(project_path)
    if "error" in model_summary:
        return {**summary, **report_summary, **model_summary}

    return {**summary, **report_summary, **model_summary}

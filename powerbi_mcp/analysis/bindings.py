import json
from pathlib import Path
from typing import Any

from powerbi_mcp.common.paths import get_project_summary_paths


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_pages_dir(project_path: str) -> Path | None:
    return get_project_summary_paths(project_path).pages_dir


def _extract_visual_title(visual_data: dict[str, Any]) -> str | None:
    objects = visual_data.get("visual", {}).get("visualContainerObjects", {})
    title_obj = objects.get("title", [])
    if not title_obj:
        return None

    title_props = title_obj[0].get("properties", {})
    title_expr = title_props.get("text", {}).get("expr", {}).get("Literal", {})
    return title_expr.get("Value", "").strip("'\"") or None


def _iter_nested_dicts(node: Any) -> list[dict[str, Any]]:
    nested: list[dict[str, Any]] = []
    if isinstance(node, dict):
        nested.append(node)
        for value in node.values():
            nested.extend(_iter_nested_dicts(value))
    elif isinstance(node, list):
        for item in node:
            nested.extend(_iter_nested_dicts(item))
    return nested


def _extract_field_reference(field: dict[str, Any]) -> tuple[str | None, str | None]:
    for candidate in _iter_nested_dicts(field):
        property_name = candidate.get("Property")
        expression = candidate.get("Expression")
        source_ref = expression.get("SourceRef") if isinstance(expression, dict) else None
        entity = source_ref.get("Entity") if isinstance(source_ref, dict) else None
        if isinstance(entity, str) and isinstance(property_name, str):
            return entity, property_name

    return None, None


def _extract_query_state_bindings(visual_data: dict[str, Any]) -> list[dict[str, Any]]:
    query_state = visual_data.get("visual", {}).get("query", {}).get("queryState", {})
    if not isinstance(query_state, dict):
        return []

    bindings: list[dict[str, Any]] = []
    for role, role_config in query_state.items():
        if not isinstance(role_config, dict):
            continue

        projections = role_config.get("projections")
        if not isinstance(projections, list):
            continue

        for projection in projections:
            if not isinstance(projection, dict):
                continue

            field = projection.get("field")
            if not isinstance(field, dict):
                continue

            entity, property_name = _extract_field_reference(field)
            if entity is None or property_name is None:
                continue

            field_type = next(
                (key for key, value in field.items() if isinstance(key, str) and isinstance(value, dict)),
                "Unknown",
            )
            bindings.append(
                {
                    "role": role,
                    "field_type": field_type,
                    "entity": entity,
                    "property": property_name,
                    "query_ref": projection.get("queryRef"),
                    "native_query_ref": projection.get("nativeQueryRef"),
                    "display_name": projection.get("displayName"),
                    "active": projection.get("active", True),
                }
            )

    return bindings


def _serialize_visual(
    *,
    page_id: str,
    page_name: str,
    visual_id: str,
    visual_path: Path,
    visual_data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "page_id": page_id,
        "page_name": page_name,
        "visual_id": visual_id,
        "visual_type": visual_data.get("visual", {}).get("visualType", "unknown"),
        "title": _extract_visual_title(visual_data),
        "path": str(visual_path),
    }


def _list_page_ids(pages_dir: Path) -> list[str]:
    meta_path = pages_dir / "pages.json"
    if meta_path.exists():
        meta = _read_json(meta_path)
        page_order = meta.get("pageOrder")
        if isinstance(page_order, list):
            return [page_id for page_id in page_order if isinstance(page_id, str)]

    return sorted(page_dir.name for page_dir in pages_dir.iterdir() if page_dir.is_dir())


def report_get_visual_bindings(project_path: str, page_id: str, visual_id: str) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None or not pages_dir.exists():
        return {"error": f"Pages directory not found in {project_path}"}

    page_json = pages_dir / page_id / "page.json"
    if not page_json.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_json = pages_dir / page_id / "visuals" / visual_id / "visual.json"
    if not visual_json.exists():
        return {"error": f"Visual not found: {visual_id}"}

    page_data = _read_json(page_json)
    visual_data = _read_json(visual_json)
    bindings = _extract_query_state_bindings(visual_data)

    return {
        **_serialize_visual(
            page_id=page_id,
            page_name=page_data.get("displayName", ""),
            visual_id=visual_id,
            visual_path=visual_json,
            visual_data=visual_data,
        ),
        "bindings": bindings,
        "count": len(bindings),
    }


def find_report_objects_by_model_reference(
    project_path: str,
    entity: str,
    property_name: str,
) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None or not pages_dir.exists():
        return {"error": f"Pages directory not found in {project_path}"}

    matches: list[dict[str, Any]] = []
    for page_id in _list_page_ids(pages_dir):
        page_json = pages_dir / page_id / "page.json"
        if not page_json.exists():
            continue

        page_data = _read_json(page_json)
        visuals_dir = pages_dir / page_id / "visuals"
        if not visuals_dir.exists():
            continue

        for visual_dir in sorted(candidate for candidate in visuals_dir.iterdir() if candidate.is_dir()):
            visual_json = visual_dir / "visual.json"
            if not visual_json.exists():
                continue

            visual_data = _read_json(visual_json)
            matching_bindings = [
                binding
                for binding in _extract_query_state_bindings(visual_data)
                if binding["entity"] == entity and binding["property"] == property_name
            ]
            if not matching_bindings:
                continue

            matches.append(
                {
                    **_serialize_visual(
                        page_id=page_id,
                        page_name=page_data.get("displayName", ""),
                        visual_id=visual_dir.name,
                        visual_path=visual_json,
                        visual_data=visual_data,
                    ),
                    "matching_bindings": matching_bindings,
                }
            )

    return {
        "entity": entity,
        "property_name": property_name,
        "matches": matches,
        "count": len(matches),
    }

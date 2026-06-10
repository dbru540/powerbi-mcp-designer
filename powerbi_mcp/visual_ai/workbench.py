from typing import Any

from powerbi_mcp.analysis.bindings import report_get_visual_bindings
from powerbi_mcp.report.read import report_list_pages, report_list_visuals
from powerbi_mcp.report.write import report_move_visual, report_update_visual_title
from powerbi_mcp.visual_ai.critic import page_design_audit
from powerbi_mcp.visual_ai.layout import page_layout_reflow_plan


TITLE_ACTION_TYPE = "set_visual_title"
LAYOUT_ACTION_TYPE = "snap_visual_to_grid"
REFLOW_ACTION_TYPE = "move_visual_to_zone"
DATA_VISUAL_TYPES = {
    "card",
    "clusteredBarChart",
    "clusteredColumnChart",
    "lineChart",
    "pieChart",
    "pivotTable",
    "slicer",
    "tableEx",
}


def _label_for_binding(binding: dict[str, Any]) -> str:
    for key in ("display_name", "native_query_ref", "property", "query_ref"):
        value = binding.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Value"


def _unique(labels: list[str]) -> list[str]:
    seen = set()
    result = []
    for label in labels:
        normalized = label.lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(label)
    return result


def _role_rank(binding: dict[str, Any]) -> int:
    role = binding.get("role")
    if role in {"Rows", "Category"}:
        return 0
    if role in {"Y", "Values"}:
        return 1
    if role in {"Columns", "Series", "Legend"}:
        return 2
    return 3


def _suggest_title(visual_type: str, bindings: list[dict[str, Any]]) -> str:
    active_bindings = [binding for binding in bindings if binding.get("active", True)]
    active_bindings.sort(key=_role_rank)
    measures = _unique(
        [
            _label_for_binding(binding)
            for binding in active_bindings
            if binding.get("field_type") in {"Measure", "Aggregation"}
        ]
    )
    dimensions = _unique(
        [
            _label_for_binding(binding)
            for binding in active_bindings
            if binding.get("field_type") == "Column"
        ]
    )

    if visual_type == "slicer" and dimensions:
        return f"Filter: {dimensions[0]}"
    if visual_type == "card" and measures:
        return measures[0]
    if measures and dimensions:
        return f"{measures[0]} by {dimensions[0]}"
    if dimensions:
        return " by ".join(dimensions[:2])
    if measures:
        return measures[0]
    return visual_type


def _snap_value(value: Any, grid_size: int) -> int:
    numeric = float(value or 0)
    return int(round(numeric / grid_size) * grid_size)


def _snap_position(position: dict[str, Any], grid_size: int) -> dict[str, int]:
    return {
        "x": max(0, _snap_value(position.get("x", 0), grid_size)),
        "y": max(0, _snap_value(position.get("y", 0), grid_size)),
        "width": max(grid_size, _snap_value(position.get("width", grid_size), grid_size)),
        "height": max(grid_size, _snap_value(position.get("height", grid_size), grid_size)),
    }


def _same_position(current: dict[str, Any], proposed: dict[str, int]) -> bool:
    return all(float(current.get(key, 0)) == float(value) for key, value in proposed.items())


def page_design_action_plan(
    project_path: str,
    page_id: str,
    audience: str | None = None,
    intent: str | None = None,
    max_actions: int = 5,
) -> dict[str, Any]:
    audit = page_design_audit(project_path, page_id, audience, intent)
    if "error" in audit:
        return audit

    visuals = report_list_visuals(project_path, page_id)
    if "error" in visuals:
        return visuals

    actions = []
    for visual in visuals["visuals"]:
        if len(actions) >= max_actions:
            break
        if visual.get("title"):
            continue

        bindings = report_get_visual_bindings(project_path, page_id, visual["id"])
        if "error" in bindings or bindings.get("count", 0) == 0:
            continue

        proposed_title = _suggest_title(visual.get("visualType", "unknown"), bindings["bindings"])
        actions.append(
            {
                "action_type": TITLE_ACTION_TYPE,
                "risk": "low",
                "requires_review": False,
                "page_id": page_id,
                "page_name": audit["page_name"],
                "visual_id": visual["id"],
                "visual_type": visual.get("visualType", "unknown"),
                "current_title": visual.get("title"),
                "proposed_title": proposed_title,
                "rationale": "Bound visuals need explicit titles so report readers can understand the metric and grain.",
                "source_dimension": "title clarity",
                "binding_count": bindings["count"],
                "bindings": bindings["bindings"],
            }
        )

    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": audit["page_name"],
        "audience": audience,
        "intent": intent,
        "audit_score": audit["score"],
        "audit_grade": audit["grade"],
        "mutates_files": False,
        "actions": actions,
        "action_count": len(actions),
    }


def page_layout_action_plan(
    project_path: str,
    page_id: str,
    grid_size: int = 8,
    max_actions: int = 5,
) -> dict[str, Any]:
    if grid_size <= 0:
        return {"error": "grid_size must be greater than zero"}

    visuals = report_list_visuals(project_path, page_id)
    if "error" in visuals:
        return visuals

    actions = []
    for visual in visuals["visuals"]:
        if len(actions) >= max_actions:
            break
        visual_type = visual.get("visualType", "unknown")
        if visual_type not in DATA_VISUAL_TYPES:
            continue

        current_position = dict(visual.get("position", {}))
        proposed_position = _snap_position(current_position, grid_size)
        if _same_position(current_position, proposed_position):
            continue

        actions.append(
            {
                "action_type": LAYOUT_ACTION_TYPE,
                "risk": "medium",
                "requires_review": True,
                "page_id": page_id,
                "visual_id": visual["id"],
                "visual_type": visual_type,
                "current_position": current_position,
                "proposed_position": proposed_position,
                "grid_size": grid_size,
                "rationale": "Snapping data visuals to a consistent grid improves alignment without changing bindings or visual type.",
                "source_dimension": "layout balance",
            }
        )

    return {
        "project_path": project_path,
        "page_id": page_id,
        "grid_size": grid_size,
        "mutates_files": False,
        "actions": actions,
        "action_count": len(actions),
    }


def _apply_action(project_path: str, action: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    if action.get("action_type") == TITLE_ACTION_TYPE:
        return report_update_visual_title(
            project_path=project_path,
            page_id=action["page_id"],
            visual_id=action["visual_id"],
            title=action["proposed_title"],
            dry_run=dry_run,
        )
    if action.get("action_type") in {LAYOUT_ACTION_TYPE, REFLOW_ACTION_TYPE}:
        position = action["proposed_position"]
        return report_move_visual(
            project_path=project_path,
            page_id=action["page_id"],
            visual_id=action["visual_id"],
            x=position["x"],
            y=position["y"],
            width=position["width"],
            height=position["height"],
            dry_run=dry_run,
        )

    return {
        "success": False,
        "error": f"Unsupported action type: {action.get('action_type')}",
        "dry_run": dry_run,
    }


def page_design_apply_quick_wins(
    project_path: str,
    page_id: str,
    audience: str | None = None,
    intent: str | None = None,
    max_actions: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = page_design_action_plan(project_path, page_id, audience, intent, max_actions)
    if "error" in plan:
        return plan

    results = []
    for action in plan["actions"]:
        results.append(
            {
                "action": action,
                "result": _apply_action(project_path, action, dry_run),
            }
        )

    failed = [item for item in results if not item["result"].get("success", False)]
    applied_count = 0 if dry_run else len(results) - len(failed)
    return {
        "success": not failed,
        "dry_run": dry_run,
        "project_path": project_path,
        "page_id": page_id,
        "page_name": plan["page_name"],
        "audience": audience,
        "intent": intent,
        "attempted_count": len(results),
        "applied_count": applied_count,
        "failed_count": len(failed),
        "results": results,
    }


def page_layout_apply_reflow_plan(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: str | None = None,
    max_moves: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = page_layout_reflow_plan(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        subject=subject,
        max_moves=max_moves,
    )
    if "error" in plan:
        return plan

    results = [
        {
            "action": action,
            "result": _apply_action(project_path, action, dry_run),
        }
        for action in plan["actions"]
    ]
    failed = [item for item in results if not item["result"].get("success", False)]
    applied_count = 0 if dry_run else len(results) - len(failed)
    return {
        "success": not failed,
        "dry_run": dry_run,
        "project_path": project_path,
        "page_id": page_id,
        "audience": audience,
        "intent": intent,
        "attempted_count": len(results),
        "applied_count": applied_count,
        "failed_count": len(failed),
        "plan": plan,
        "results": results,
    }


def page_layout_apply_quick_wins(
    project_path: str,
    page_id: str,
    grid_size: int = 8,
    max_actions: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = page_layout_action_plan(project_path, page_id, grid_size, max_actions)
    if "error" in plan:
        return plan

    results = [
        {
            "action": action,
            "result": _apply_action(project_path, action, dry_run),
        }
        for action in plan["actions"]
    ]
    failed = [item for item in results if not item["result"].get("success", False)]
    applied_count = 0 if dry_run else len(results) - len(failed)
    return {
        "success": not failed,
        "dry_run": dry_run,
        "project_path": project_path,
        "page_id": page_id,
        "grid_size": grid_size,
        "attempted_count": len(results),
        "applied_count": applied_count,
        "failed_count": len(failed),
        "results": results,
    }


def report_design_apply_quick_wins(
    project_path: str,
    audience: str | None = None,
    intent: str | None = None,
    page_limit: int | None = None,
    max_actions_per_page: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    pages = report_list_pages(project_path)
    if "error" in pages:
        return pages

    selected_pages = pages["pages"][:page_limit] if page_limit is not None else pages["pages"]
    page_results = [
        page_design_apply_quick_wins(
            project_path,
            page["id"],
            audience=audience,
            intent=intent,
            max_actions=max_actions_per_page,
            dry_run=dry_run,
        )
        for page in selected_pages
    ]
    failed = [result for result in page_results if not result.get("success", False)]
    return {
        "success": not failed,
        "dry_run": dry_run,
        "project_path": project_path,
        "audience": audience,
        "intent": intent,
        "page_count": len(page_results),
        "attempted_count": sum(result.get("attempted_count", 0) for result in page_results),
        "applied_count": sum(result.get("applied_count", 0) for result in page_results),
        "failed_count": sum(result.get("failed_count", 0) for result in page_results),
        "page_results": page_results,
    }


def report_layout_apply_quick_wins(
    project_path: str,
    page_limit: int | None = None,
    grid_size: int = 8,
    max_actions_per_page: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    pages = report_list_pages(project_path)
    if "error" in pages:
        return pages

    selected_pages = pages["pages"][:page_limit] if page_limit is not None else pages["pages"]
    page_results = [
        page_layout_apply_quick_wins(
            project_path,
            page["id"],
            grid_size=grid_size,
            max_actions=max_actions_per_page,
            dry_run=dry_run,
        )
        for page in selected_pages
    ]
    failed = [result for result in page_results if not result.get("success", False)]
    return {
        "success": not failed,
        "dry_run": dry_run,
        "project_path": project_path,
        "page_count": len(page_results),
        "grid_size": grid_size,
        "attempted_count": sum(result.get("attempted_count", 0) for result in page_results),
        "applied_count": sum(result.get("applied_count", 0) for result in page_results),
        "failed_count": sum(result.get("failed_count", 0) for result in page_results),
        "page_results": page_results,
    }

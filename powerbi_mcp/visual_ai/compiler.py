from typing import Any

from powerbi_mcp.report.write import report_create_visual
from powerbi_mcp.visual_ai.planner import visual_plan_generate


SUPPORTED_APPLY_TYPES = {
    "barChart",
    "card",
    "columnChart",
    "lineChart",
    "clusteredBarChart",
    "clusteredColumnChart",
    "donutChart",
    "image",
    "pieChart",
    "pivotTable",
    "scatterChart",
    "shape",
    "slicer",
    "tableEx",
    "textbox",
}


def _extract_binding(assignments: dict[str, list[dict[str, Any]]], role: str) -> dict[str, Any] | None:
    values = assignments.get(role, [])
    if not values:
        return None
    return values[0]


def visual_plan_apply(
    project_path: str,
    page_id: str,
    plan: dict[str, Any],
    x: int = 0,
    y: int = 0,
    width: int | None = None,
    height: int | None = None,
    title: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    generation_path = plan.get("generation_path")
    if generation_path != "native-pbir":
        return {
            "error": f"Unsupported generation path for apply: {generation_path}",
        }

    requirements = plan.get("requirements")
    if isinstance(requirements, dict) and not requirements.get("ok", False):
        return {
            "error": "Visual plan requirements are not satisfied",
            "requirements": requirements,
        }

    visual_type = plan.get("recommended_visual_type")
    if visual_type not in SUPPORTED_APPLY_TYPES:
        return {
            "error": f"Visual plan apply is not yet supported for visual type: {visual_type}",
        }

    assignments = plan.get("suggested_assignments", {})
    category = _extract_binding(assignments, "Category")
    measure = _extract_binding(assignments, "Y")
    layout_defaults = plan.get("layout_defaults", {})

    final_width = width if width is not None else layout_defaults.get("width", 320)
    final_height = height if height is not None else layout_defaults.get("height", 240)

    visual_title = title
    if visual_title is None:
        if visual_type == "card":
            visual_title = plan.get("intent", "KPI")
        elif visual_type in {"shape", "image"}:
            visual_title = None
        else:
            visual_title = plan.get("intent", "Generated visual")

    result = report_create_visual(
        project_path=project_path,
        page_id=page_id,
        visual_type=visual_type,
        x=x,
        y=y,
        width=final_width,
        height=final_height,
        title=visual_title,
        category_entity=category.get("entity") if category else None,
        category_property=category.get("property") if category else None,
        measure_entity=measure.get("entity") if measure else None,
        measure_property=measure.get("property") if measure else None,
        role_assignments=assignments,
        dry_run=dry_run,
    )
    if "error" in result or not result.get("success", False):
        return result

    return {
        "success": True,
        "dry_run": dry_run,
        "page_id": page_id,
        "visual_type": visual_type,
        "plan": plan,
        "applied_result": result,
    }


def visual_plan_generate_and_apply(
    project_path: str,
    page_id: str,
    intent: str,
    dimensions: list[dict[str, Any]] | None = None,
    measures: list[dict[str, Any]] | None = None,
    audience: str | None = None,
    preferred_path: str | None = None,
    template_project_path: str | None = None,
    x: int = 0,
    y: int = 0,
    width: int | None = None,
    height: int | None = None,
    title: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    plan = visual_plan_generate(
        intent=intent,
        dimensions=dimensions,
        measures=measures,
        audience=audience,
        preferred_path=preferred_path,
        template_project_path=template_project_path,
    )
    if plan.get("requirements") and not plan["requirements"].get("ok", False):
        return {
            "error": "Generated plan has unsatisfied requirements",
            "plan": plan,
        }

    return visual_plan_apply(
        project_path=project_path,
        page_id=page_id,
        plan=plan,
        x=x,
        y=y,
        width=width,
        height=height,
        title=title,
        dry_run=dry_run,
    )

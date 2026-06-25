from typing import Any

from powerbi_mcp.visual_ai.catalog import SUPPORTED_VISUALS, visual_requirements_check
from powerbi_mcp.visual_ai.examples import visual_template_recommend


def _pick_visual_type(intent: str, dimensions: list[dict[str, Any]], measures: list[dict[str, Any]]) -> str:
    lowered = intent.lower()
    if any(keyword in lowered for keyword in ("image", "logo", "icon", "brand")):
        return "image"
    if any(keyword in lowered for keyword in ("shape", "panel", "background", "separator", "divider")):
        return "shape"
    if any(keyword in lowered for keyword in ("text", "comment", "narrative", "intro", "header")):
        return "textbox"
    if any(keyword in lowered for keyword in ("filter", "slicer", "selector")):
        return "slicer"
    if any(keyword in lowered for keyword in ("pivot", "matrix", "cross-tab", "crosstab")) and dimensions and measures:
        return "pivotTable"
    if any(keyword in lowered for keyword in ("detail", "record", "table", "list")) and (dimensions or measures):
        return "tableEx"
    if any(keyword in lowered for keyword in ("scatter", "correlation", "relationship", "bubble", "x vs y", "xy plot")) and len(measures) >= 2:
        return "scatterChart"
    if "donut" in lowered and dimensions and measures:
        return "donutChart"
    if "pie" in lowered and dimensions and measures:
        return "pieChart"
    if any(keyword in lowered for keyword in ("share", "part-to-whole", "composition")) and dimensions and measures:
        return "donutChart"
    if any(keyword in lowered for keyword in ("horizontal bar", "bar ranking", "bar chart")) and dimensions and measures:
        return "barChart"
    if any(keyword in lowered for keyword in ("vertical column", "column chart")) and dimensions and measures:
        return "columnChart"
    if any(keyword in lowered for keyword in ("trend", "monthly", "daily", "timeline", "over time")) and dimensions and measures:
        return "lineChart"
    if any(keyword in lowered for keyword in ("compare", "comparison", "rank", "ranking", "top")) and dimensions and measures:
        return "clusteredColumnChart"
    if not dimensions and measures:
        return "card"
    if dimensions and measures:
        return "clusteredColumnChart"
    return "tableEx"


def _suggest_assignments(visual_type: str, dimensions: list[dict[str, Any]], measures: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if visual_type == "card":
        return {"Values": measures[:1]}
    if visual_type == "lineChart":
        assignments = {
            "Category": dimensions[:1],
            "Y": measures[:1],
        }
        if len(dimensions) > 1:
            assignments["Series"] = dimensions[1:2]
        return assignments
    if visual_type in {
        "barChart",
        "columnChart",
        "clusteredBarChart",
        "clusteredColumnChart",
        "donutChart",
        "pieChart",
    }:
        assignments = {
            "Category": dimensions[:1],
            "Y": measures[:1],
        }
        if visual_type not in {"donutChart", "pieChart"} and len(dimensions) > 1:
            assignments["Series"] = dimensions[1:2]
        return assignments
    if visual_type == "scatterChart":
        assignments = {"X": measures[:1], "Y": measures[1:2]}
        if dimensions:
            assignments["Category"] = dimensions[:1]
        if len(measures) > 2:
            assignments["Size"] = measures[2:3]
        if len(dimensions) > 1:
            assignments["Series"] = dimensions[1:2]
        return assignments
    if visual_type == "pivotTable":
        assignments = {
            "Rows": dimensions[:1],
            "Values": measures,
        }
        if len(dimensions) > 1:
            assignments["Columns"] = dimensions[1:2]
        return assignments
    if visual_type == "slicer":
        return {"Values": dimensions[:1]}
    if visual_type == "tableEx":
        return {"Values": (dimensions + measures)}
    return {}


def visual_plan_generate(
    intent: str,
    dimensions: list[dict[str, Any]] | None = None,
    measures: list[dict[str, Any]] | None = None,
    audience: str | None = None,
    preferred_path: str | None = None,
    template_project_path: str | None = None,
) -> dict[str, Any]:
    dimensions = dimensions or []
    measures = measures or []

    if preferred_path == "deneb":
        plan = {
            "intent": intent,
            "audience": audience,
            "generation_path": "deneb",
            "recommended_visual_type": "deneb",
            "confidence": 0.72,
            "rationale": "Preferred path explicitly requested as Deneb for declarative chart generation.",
            "suggested_assignments": {},
            "requirements": None,
            "model_work_required": False,
        }
        if template_project_path:
            plan["template_reference"] = None
        return plan

    visual_type = _pick_visual_type(intent, dimensions, measures)
    suggested_assignments = _suggest_assignments(visual_type, dimensions, measures)
    requirements = visual_requirements_check(visual_type, suggested_assignments)
    config = SUPPORTED_VISUALS[visual_type]

    rationale_parts = [config["description"]]
    if audience:
        rationale_parts.append(f"Audience hint: {audience}.")
    if visual_type == "lineChart":
        rationale_parts.append("Intent suggests a trend-oriented presentation.")
    elif visual_type == "card":
        rationale_parts.append("Single-measure intent favors a KPI presentation.")
    elif visual_type in {"barChart", "columnChart", "clusteredBarChart", "clusteredColumnChart"}:
        rationale_parts.append("Intent suggests a category comparison view.")
    elif visual_type in {"donutChart", "pieChart"}:
        rationale_parts.append("Intent suggests a simple part-to-whole composition view.")
    elif visual_type == "scatterChart":
        rationale_parts.append("Intent suggests a correlation view across two measures.")
    elif visual_type == "pivotTable":
        rationale_parts.append("Intent suggests an analyst matrix with row, column, and measure intersections.")
    elif visual_type == "slicer":
        rationale_parts.append("Intent is control-oriented rather than analytical.")
    elif visual_type in {"shape", "image", "textbox"}:
        rationale_parts.append("Intent is presentation-oriented rather than data-bound.")

    plan = {
        "intent": intent,
        "audience": audience,
        "generation_path": config["generation_path"],
        "recommended_visual_type": visual_type,
        "confidence": 0.86 if requirements["ok"] else 0.62,
        "rationale": " ".join(rationale_parts),
        "suggested_assignments": suggested_assignments,
        "requirements": requirements,
        "model_work_required": False,
        "layout_defaults": dict(config["layout_defaults"]),
    }
    if template_project_path:
        plan["template_reference"] = visual_template_recommend(
            template_project_path,
            visual_type,
        )
    return plan

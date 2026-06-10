from typing import Any

from powerbi_mcp.report.read import report_list_pages, report_list_visuals
from powerbi_mcp.visual_ai.design_expert import report_design_brief_generate


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


def _area(position: dict[str, Any]) -> float:
    return max(0.0, float(position.get("width", 0))) * max(0.0, float(position.get("height", 0)))


def _rect(position: dict[str, Any]) -> tuple[float, float, float, float]:
    x = float(position.get("x", 0))
    y = float(position.get("y", 0))
    return (
        x,
        y,
        x + float(position.get("width", 0)),
        y + float(position.get("height", 0)),
    )


def _overlap_area(left: dict[str, Any], right: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = _rect(left)
    bx1, by1, bx2, by2 = _rect(right)
    overlap_width = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_height = max(0.0, min(ay2, by2) - max(ay1, by1))
    return overlap_width * overlap_height


def _zone_for_position(position: dict[str, Any], page_width: int, page_height: int) -> str:
    x = float(position.get("x", 0))
    y = float(position.get("y", 0))
    center_x = x + float(position.get("width", 0)) / 2
    center_y = y + float(position.get("height", 0)) / 2

    if center_y <= page_height * 0.15:
        return "header"
    if center_x <= page_width * 0.28:
        return "left_rail"
    if center_y >= page_height * 0.82:
        return "detail_band"
    return "main_stage"


def _page_metadata(project_path: str, page_id: str) -> dict[str, Any] | None:
    pages = report_list_pages(project_path)
    if "error" in pages:
        return None
    return next((page for page in pages["pages"] if page["id"] == page_id), None)


def _zone_summary(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for item in items:
        zone = item["zone"]
        bucket = summary.setdefault(zone, {"visual_count": 0, "data_visual_count": 0, "area": 0.0})
        bucket["visual_count"] += 1
        bucket["area"] = round(bucket["area"] + item["area"], 2)
        if item["is_data_visual"]:
            bucket["data_visual_count"] += 1
    return summary


def page_layout_analyze(
    project_path: str,
    page_id: str,
    overlap_threshold: float = 25.0,
) -> dict[str, Any]:
    page = _page_metadata(project_path, page_id)
    if page is None:
        return {"error": f"Page not found: {page_id}"}

    visuals = report_list_visuals(project_path, page_id)
    if "error" in visuals:
        return visuals

    page_width = int(page.get("width", 1280))
    page_height = int(page.get("height", 720))
    visual_zones = []
    for visual in visuals["visuals"]:
        position = visual.get("position", {})
        visual_type = visual.get("visualType", "unknown")
        area = round(_area(position), 2)
        visual_zones.append(
            {
                "visual_id": visual["id"],
                "visual_type": visual_type,
                "title": visual.get("title"),
                "position": position,
                "zone": _zone_for_position(position, page_width, page_height),
                "area": area,
                "area_ratio": round(area / (page_width * page_height), 4),
                "is_data_visual": visual_type in DATA_VISUAL_TYPES,
            }
        )

    overlaps = []
    for index, left in enumerate(visual_zones):
        for right in visual_zones[index + 1:]:
            overlap = round(_overlap_area(left["position"], right["position"]), 2)
            if overlap <= overlap_threshold:
                continue
            overlaps.append(
                {
                    "left_visual_id": left["visual_id"],
                    "right_visual_id": right["visual_id"],
                    "left_visual_type": left["visual_type"],
                    "right_visual_type": right["visual_type"],
                    "overlap_area": overlap,
                    "severity": "warning" if overlap >= 500 else "info",
                }
            )

    focal_candidates = sorted(
        [item for item in visual_zones if item["is_data_visual"]],
        key=lambda item: item["area"],
        reverse=True,
    )[:5]
    zone_summary = _zone_summary(visual_zones)
    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": page.get("displayName", ""),
        "page_size": {"width": page_width, "height": page_height},
        "visual_count": visuals["count"],
        "visual_zones": visual_zones,
        "zone_summary": zone_summary,
        "overlaps": overlaps,
        "overlap_count": len(overlaps),
        "focal_candidates": focal_candidates,
    }


def _zone_rect(zone: str, page_width: int, page_height: int) -> dict[str, int]:
    if zone == "hero":
        return {"x": 32, "y": 32, "width": page_width - 64, "height": 128}
    if zone == "trend":
        return {"x": 32, "y": 184, "width": int(page_width * 0.58), "height": 284}
    if zone == "breakdown":
        return {"x": int(page_width * 0.64), "y": 184, "width": int(page_width * 0.33), "height": 284}
    if zone == "controls":
        return {"x": 32, "y": page_height - 124, "width": page_width - 64, "height": 92}
    if zone == "status":
        return {"x": 32, "y": 32, "width": page_width - 64, "height": 112}
    if zone == "exceptions":
        return {"x": 32, "y": 168, "width": int(page_width * 0.44), "height": 280}
    if zone == "context":
        return {"x": 32, "y": 32, "width": page_width - 64, "height": 96}
    if zone == "comparison":
        return {"x": 32, "y": 152, "width": int(page_width * 0.46), "height": 300}
    if zone == "main":
        return {"x": 32, "y": 168, "width": page_width - 64, "height": 332}
    return {"x": 32, "y": page_height - 220, "width": page_width - 64, "height": 188}


def page_layout_blueprint_generate(
    audience: str,
    intent: str,
    subject: str | None = None,
    page_width: int = 1280,
    page_height: int = 720,
) -> dict[str, Any]:
    brief = report_design_brief_generate(audience=audience, intent=intent, subject=subject)
    zones = []
    for index, section in enumerate(brief["sections"], start=1):
        zones.append(
            {
                **section,
                "priority": index,
                "rect": _zone_rect(section["zone"], page_width, page_height),
            }
        )
    return {
        "audience": audience,
        "intent": intent,
        "subject": subject,
        "page_size": {"width": page_width, "height": page_height},
        "page_archetype": brief["page_archetype"],
        "narrative_flow": brief["narrative_flow"],
        "zones": zones,
        "style_guidance": brief["style_guidance"],
    }


def page_layout_recommend(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: str | None = None,
) -> dict[str, Any]:
    analysis = page_layout_analyze(project_path, page_id)
    if "error" in analysis:
        return analysis

    size = analysis["page_size"]
    blueprint = page_layout_blueprint_generate(
        audience=audience,
        intent=intent,
        subject=subject,
        page_width=size["width"],
        page_height=size["height"],
    )
    recommendations = []
    if analysis["overlap_count"]:
        recommendations.append(
            {
                "type": "overlap_review",
                "severity": "warning",
                "evidence": f"{analysis['overlap_count']} overlapping visual pairs detected.",
                "recommendation": "Review overlap pairs before applying any automated reflow.",
            }
        )
    if analysis["visual_count"] > 12:
        recommendations.append(
            {
                "type": "density_reduction",
                "severity": "warning",
                "evidence": f"Page has {analysis['visual_count']} visuals.",
                "recommendation": "Move supporting details to a lower-priority page or detail band.",
            }
        )
    if "main_stage" not in analysis["zone_summary"]:
        recommendations.append(
            {
                "type": "focal_path",
                "severity": "warning",
                "evidence": "No current visual is centered in the main stage.",
                "recommendation": "Promote one primary visual into the main stage zone.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "type": "preserve_structure",
                "severity": "info",
                "evidence": "Current page has no major geometric issues.",
                "recommendation": "Use the blueprint as a style reference rather than a forced reflow.",
            }
        )

    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": analysis["page_name"],
        "audience": audience,
        "intent": intent,
        "mutates_files": False,
        "analysis": analysis,
        "blueprint": blueprint,
        "recommendations": recommendations,
        "recommendation_count": len(recommendations),
    }


def _visual_matches_zone(visual_type: str, recommended_visuals: list[str]) -> bool:
    if visual_type in recommended_visuals:
        return True
    compatible = {
        "clusteredBarChart": {"clusteredColumnChart"},
        "clusteredColumnChart": {"clusteredBarChart"},
        "pivotTable": {"tableEx"},
        "tableEx": {"pivotTable"},
    }
    return bool(compatible.get(visual_type, set()).intersection(recommended_visuals))


def page_layout_reflow_plan(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: str | None = None,
    max_moves: int = 5,
) -> dict[str, Any]:
    recommendation = page_layout_recommend(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        subject=subject,
    )
    if "error" in recommendation:
        return recommendation

    visuals = [
        visual
        for visual in recommendation["analysis"]["visual_zones"]
        if visual["is_data_visual"]
    ]
    used_visual_ids = set()
    actions = []
    for zone in recommendation["blueprint"]["zones"]:
        if len(actions) >= max_moves:
            break
        recommended_visuals = zone.get("recommended_visuals", [])
        candidates = [
            visual
            for visual in visuals
            if visual["visual_id"] not in used_visual_ids
            and _visual_matches_zone(visual["visual_type"], recommended_visuals)
        ]
        if not candidates:
            continue

        selected = sorted(candidates, key=lambda item: item["area"], reverse=True)[0]
        used_visual_ids.add(selected["visual_id"])
        actions.append(
            {
                "action_type": "move_visual_to_zone",
                "risk": "high",
                "requires_review": True,
                "page_id": page_id,
                "visual_id": selected["visual_id"],
                "visual_type": selected["visual_type"],
                "current_zone": selected["zone"],
                "target_zone": zone["zone"],
                "current_position": selected["position"],
                "proposed_position": dict(zone["rect"]),
                "rationale": (
                    f"Move {selected['visual_type']} into the {zone['zone']} zone "
                    f"for the {recommendation['blueprint']['page_archetype']} narrative."
                ),
                "source_dimension": "visual hierarchy",
            }
        )

    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": recommendation["page_name"],
        "audience": audience,
        "intent": intent,
        "mutates_files": False,
        "analysis": recommendation["analysis"],
        "blueprint": recommendation["blueprint"],
        "recommendations": recommendation["recommendations"],
        "actions": actions,
        "action_count": len(actions),
    }

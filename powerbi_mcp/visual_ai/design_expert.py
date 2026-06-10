def _classify_archetype(audience: str, intent: str) -> str:
    a = audience.lower()
    i = intent.lower()
    if "executive" in a or "direction" in a or "overview" in i:
        return "executive-overview"
    if "operations" in a or "monitor" in i:
        return "operational-monitor"
    if "analyst" in a or "diagnos" in i or "analysis" in i:
        return "analytical-deep-dive"
    return "balanced-overview"


def report_design_brief_generate(
    audience: str,
    intent: str,
    subject: str | None = None,
) -> dict:
    archetype = _classify_archetype(audience, intent)

    if archetype == "executive-overview":
        sections = [
            {"zone": "hero", "purpose": "headline KPIs", "recommended_visuals": ["card"]},
            {"zone": "trend", "purpose": "time trend", "recommended_visuals": ["lineChart"]},
            {"zone": "breakdown", "purpose": "key category comparison", "recommended_visuals": ["clusteredColumnChart"]},
            {"zone": "controls", "purpose": "high-value filters", "recommended_visuals": ["slicer"]},
        ]
        style_guidance = [
            "Use strong KPI hierarchy with one dominant hero row.",
            "Limit the page to one main trend and one main breakdown.",
            "Favor whitespace and short labels over dense detail.",
        ]
    elif archetype == "operational-monitor":
        sections = [
            {"zone": "controls", "purpose": "persistent operational filters", "recommended_visuals": ["slicer"]},
            {"zone": "status", "purpose": "current status KPIs", "recommended_visuals": ["card"]},
            {"zone": "exceptions", "purpose": "outlier comparison", "recommended_visuals": ["clusteredBarChart"]},
            {"zone": "detail", "purpose": "record-level inspection", "recommended_visuals": ["tableEx"]},
        ]
        style_guidance = [
            "Prioritize scanability and quick exception detection.",
            "Keep filters visible and stable across the page.",
            "Use tables only for the lower-detail zone.",
        ]
    elif archetype == "analytical-deep-dive":
        sections = [
            {"zone": "context", "purpose": "question framing", "recommended_visuals": ["textbox"]},
            {"zone": "comparison", "purpose": "category comparison", "recommended_visuals": ["clusteredColumnChart"]},
            {"zone": "trend", "purpose": "time trend or sequence", "recommended_visuals": ["lineChart"]},
            {"zone": "detail", "purpose": "supporting detail", "recommended_visuals": ["tableEx"]},
        ]
        style_guidance = [
            "Use the top of the page to explain the analytical question.",
            "Let comparison and trend views answer different parts of the story.",
            "Reserve detailed tables for the bottom of the page.",
        ]
    else:
        sections = [
            {"zone": "hero", "purpose": "summary and orientation", "recommended_visuals": ["card", "textbox"]},
            {"zone": "main", "purpose": "primary chart", "recommended_visuals": ["lineChart", "clusteredColumnChart"]},
            {"zone": "detail", "purpose": "supporting detail or filter", "recommended_visuals": ["tableEx", "slicer"]},
        ]
        style_guidance = [
            "Balance readability with analytical depth.",
            "Avoid mixing too many chart types in the same visual zone.",
            "Use clear section headers and one primary narrative per page.",
        ]

    return {
        "audience": audience,
        "intent": intent,
        "subject": subject,
        "page_archetype": archetype,
        "narrative_flow": [section["zone"] for section in sections],
        "sections": sections,
        "style_guidance": style_guidance,
    }

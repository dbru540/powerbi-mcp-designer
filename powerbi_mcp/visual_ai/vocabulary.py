from typing import Any


VOCABULARY: dict[str, dict[str, Any]] = {
    "monitor status": {
        "keywords": {"monitor", "status", "sla", "exception", "exceptions", "overdue", "alert", "daily", "cockpit"},
        "recommended_visual_families": ["card", "lineChart", "tableEx", "slicer"],
    },
    "trend": {
        "keywords": {"trend", "monthly", "daily", "weekly", "timeline", "over time", "evolution"},
        "recommended_visual_families": ["lineChart", "card"],
    },
    "rank": {
        "keywords": {"rank", "ranking", "top", "bottom", "leader", "highest", "lowest"},
        "recommended_visual_families": ["clusteredBarChart", "tableEx"],
    },
    "compare": {
        "keywords": {"compare", "comparison", "versus", "vs", "by category", "breakdown"},
        "recommended_visual_families": ["clusteredColumnChart", "clusteredBarChart", "tableEx"],
    },
    "explain variance": {
        "keywords": {"variance", "gap", "delta", "difference", "explain"},
        "recommended_visual_families": ["clusteredColumnChart", "lineChart", "tableEx"],
    },
    "inspect detail": {
        "keywords": {"detail", "details", "list", "records", "data", "inspect", "look at"},
        "recommended_visual_families": ["tableEx", "slicer"],
    },
}


def _matches(intent: str, keywords: set[str]) -> list[str]:
    lowered = intent.lower()
    return sorted(keyword for keyword in keywords if keyword in lowered)


def _merge_visuals(intents: list[str]) -> list[str]:
    visuals: list[str] = []
    for intent in intents:
        for visual in VOCABULARY[intent]["recommended_visual_families"]:
            if visual not in visuals:
                visuals.append(visual)
    return visuals


def visual_vocabulary_classify(intent: str, audience: str | None = None) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    for intent_name, config in VOCABULARY.items():
        terms = _matches(intent, config["keywords"])
        if terms:
            matched.append(
                {
                    "intent": intent_name,
                    "matched_terms": terms,
                    "weight": len(terms),
                }
            )

    if not matched:
        matched = [{"intent": "inspect detail", "matched_terms": [], "weight": 0}]

    matched.sort(key=lambda item: (-item["weight"], item["intent"]))
    intents = [item["intent"] for item in matched]

    if "monitor status" in intents and "inspect detail" not in intents:
        intents.append("inspect detail")

    primary = intents[0]
    if matched[0]["weight"] == 0:
        confidence = 0.62
    elif primary == "inspect detail" and set(matched[0]["matched_terms"]).issubset({"data", "look at"}):
        confidence = 0.62
    else:
        confidence = min(0.95, 0.65 + matched[0]["weight"] * 0.1)

    return {
        "intent": intent,
        "audience": audience,
        "primary_intent": primary,
        "intents": intents,
        "matched_terms": matched,
        "confidence": confidence,
        "recommended_visual_families": _merge_visuals(intents),
    }

from copy import deepcopy
from typing import Any


SUPPORTED_VISUALS: dict[str, dict[str, Any]] = {
    "card": {
        "visual_type": "card",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Single KPI callout for one primary measure.",
        "required_roles": [
            {"name": "Values", "kind": "measure"},
        ],
        "optional_roles": [],
        "layout_defaults": {"width": 220, "height": 120},
        "page_archetypes": ["executive-overview", "kpi-strip"],
    },
    "lineChart": {
        "visual_type": "lineChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Trend over time or ordered category with one primary measure.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Series", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 480, "height": 280},
        "page_archetypes": ["trend-analysis", "executive-overview"],
    },
    "clusteredBarChart": {
        "visual_type": "clusteredBarChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Category comparison chart optimized for longer category labels.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Series", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 480, "height": 300},
        "page_archetypes": ["comparison", "ranking"],
    },
    "clusteredColumnChart": {
        "visual_type": "clusteredColumnChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Category comparison chart optimized for short category labels and trends by bucket.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Series", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 480, "height": 300},
        "page_archetypes": ["comparison", "ranking"],
    },
    "barChart": {
        "visual_type": "barChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Horizontal category comparison chart for rankings and long labels.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Series", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 560, "height": 320},
        "page_archetypes": ["comparison", "ranking"],
    },
    "columnChart": {
        "visual_type": "columnChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Vertical category comparison chart for compact labels or ordered buckets.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Series", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 520, "height": 300},
        "page_archetypes": ["comparison", "ranking"],
    },
    "pieChart": {
        "visual_type": "pieChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Part-to-whole chart for a small number of categories.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [],
        "layout_defaults": {"width": 320, "height": 260},
        "page_archetypes": ["composition", "supporting-detail"],
    },
    "donutChart": {
        "visual_type": "donutChart",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Part-to-whole chart with center space for simple share narratives.",
        "required_roles": [
            {"name": "Category", "kind": "dimension"},
            {"name": "Y", "kind": "measure"},
        ],
        "optional_roles": [],
        "layout_defaults": {"width": 320, "height": 260},
        "page_archetypes": ["composition", "executive-overview"],
    },
    "tableEx": {
        "visual_type": "tableEx",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Detailed tabular view for record inspection or supporting detail.",
        "required_roles": [
            {"name": "Values", "kind": "any"},
        ],
        "optional_roles": [],
        "layout_defaults": {"width": 560, "height": 320},
        "page_archetypes": ["detail", "supporting-detail"],
    },
    "pivotTable": {
        "visual_type": "pivotTable",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Matrix-style analytical grid with rows, optional columns, and measures.",
        "required_roles": [
            {"name": "Rows", "kind": "dimension"},
            {"name": "Values", "kind": "measure"},
        ],
        "optional_roles": [
            {"name": "Columns", "kind": "dimension"},
        ],
        "layout_defaults": {"width": 760, "height": 360},
        "page_archetypes": ["analyst-workbench", "detail"],
    },
    "slicer": {
        "visual_type": "slicer",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Interactive page-level filter for one dimension.",
        "required_roles": [
            {"name": "Values", "kind": "dimension"},
        ],
        "optional_roles": [],
        "layout_defaults": {"width": 200, "height": 90},
        "page_archetypes": ["control-panel", "overview"],
    },
    "textbox": {
        "visual_type": "textbox",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Narrative heading, commentary, or instruction block.",
        "required_roles": [],
        "optional_roles": [],
        "layout_defaults": {"width": 420, "height": 80},
        "page_archetypes": ["narrative", "section-header"],
    },
    "shape": {
        "visual_type": "shape",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Presentation shape for panels, separators, grouping, and visual hierarchy.",
        "required_roles": [],
        "optional_roles": [],
        "layout_defaults": {"width": 320, "height": 120},
        "page_archetypes": ["visual-structure", "section-background"],
    },
    "image": {
        "visual_type": "image",
        "syntax_family": "native-pbir",
        "generation_path": "native-pbir",
        "description": "Presentation image placeholder for logos, icons, and branded context.",
        "required_roles": [],
        "optional_roles": [],
        "layout_defaults": {"width": 160, "height": 80},
        "page_archetypes": ["branding", "narrative"],
    },
}


def _normalize_kind(value: str | None) -> str:
    if value is None:
        return "unknown"
    lowered = value.lower()
    if lowered in {"measure", "value", "metric"}:
        return "measure"
    if lowered in {"dimension", "category", "column", "attribute"}:
        return "dimension"
    return lowered


def visual_catalog_list() -> dict[str, Any]:
    visuals = []
    for visual_id, config in SUPPORTED_VISUALS.items():
        entry = deepcopy(config)
        entry["id"] = visual_id
        visuals.append(entry)
    return {"visuals": visuals, "count": len(visuals)}


def visual_requirements_check(
    visual_type: str,
    assignments: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    config = SUPPORTED_VISUALS.get(visual_type)
    if config is None:
        return {"error": f"Unsupported visual type: {visual_type}"}

    assignments = assignments or {}
    missing_roles: list[str] = []
    invalid_roles: list[dict[str, Any]] = []

    for role in config["required_roles"]:
        role_name = role["name"]
        expected_kind = role["kind"]
        provided = assignments.get(role_name, [])
        if not provided:
            missing_roles.append(role_name)
            continue

        if expected_kind == "any":
            continue

        for binding in provided:
            actual_kind = _normalize_kind(binding.get("kind"))
            if actual_kind != expected_kind:
                invalid_roles.append(
                    {
                        "role": role_name,
                        "expected_kind": expected_kind,
                        "actual_kind": actual_kind,
                        "binding": binding,
                    }
                )

    return {
        "visual_type": visual_type,
        "ok": len(missing_roles) == 0 and len(invalid_roles) == 0,
        "required_roles": deepcopy(config["required_roles"]),
        "optional_roles": deepcopy(config["optional_roles"]),
        "missing_roles": missing_roles,
        "invalid_roles": invalid_roles,
    }

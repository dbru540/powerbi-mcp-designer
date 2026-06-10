import json
from collections import Counter
from pathlib import Path
from typing import Any

from powerbi_mcp.analysis.bindings import _extract_query_state_bindings, _extract_visual_title
from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.visual_ai.catalog import SUPPORTED_VISUALS


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _list_page_ids(pages_dir: Path) -> list[str]:
    meta_path = pages_dir / "pages.json"
    if meta_path.exists():
        meta = _read_json(meta_path)
        page_order = meta.get("pageOrder")
        if isinstance(page_order, list):
            return [page_id for page_id in page_order if isinstance(page_id, str)]

    return sorted(page_dir.name for page_dir in pages_dir.iterdir() if page_dir.is_dir())


def _page_name(page_json: Path) -> str:
    if not page_json.exists():
        return ""
    page_data = _read_json(page_json)
    return page_data.get("displayName", "")


def _layout_from_visual(visual_data: dict[str, Any]) -> dict[str, Any]:
    position = visual_data.get("position", {})
    return {
        "x": position.get("x", 0),
        "y": position.get("y", 0),
        "z": position.get("z", 0),
        "width": position.get("width", 0),
        "height": position.get("height", 0),
    }


def _query_roles(bindings: list[dict[str, Any]]) -> list[str]:
    return sorted({binding["role"] for binding in bindings if binding.get("role")})


def _object_groups(visual: dict[str, Any]) -> dict[str, list[str]]:
    objects = visual.get("objects", {})
    container_objects = visual.get("visualContainerObjects", {})
    return {
        "objects": sorted(objects.keys()) if isinstance(objects, dict) else [],
        "visualContainerObjects": sorted(container_objects.keys())
        if isinstance(container_objects, dict)
        else [],
    }


def _has_filters(visual_data: dict[str, Any]) -> bool:
    filter_config = visual_data.get("filterConfig", {})
    if isinstance(filter_config, dict) and filter_config.get("filters"):
        return True

    objects = visual_data.get("visual", {}).get("objects", {})
    if not isinstance(objects, dict):
        return False

    general_objects = objects.get("general", [])
    if not isinstance(general_objects, list):
        return False

    return any(
        isinstance(item, dict) and "filter" in item.get("properties", {})
        for item in general_objects
    )


def _score_template(example: dict[str, Any]) -> int:
    score = len(example["bindings"])
    if example["title"]:
        score += 1
    if example["has_sort"]:
        score += 1
    if example["has_filters"]:
        score += 1
    if example["object_groups"]["objects"]:
        score += 1
    if example["object_groups"]["visualContainerObjects"]:
        score += 1
    return score


def _compact_style_defaults(examples: list[dict[str, Any]]) -> dict[str, Any]:
    objects: dict[str, Any] = {}
    container_objects: dict[str, Any] = {}
    object_group_counts: Counter[str] = Counter()
    container_group_counts: Counter[str] = Counter()

    for example in sorted(examples, key=lambda item: (-item["template_score"], item["visual_id"])):
        visual_data = _read_json(Path(example["path"]))
        visual = visual_data.get("visual", {})
        visual_objects = visual.get("objects", {})
        if isinstance(visual_objects, dict):
            for group, value in visual_objects.items():
                object_group_counts[group] += 1
                if group not in objects and isinstance(value, list) and value:
                    objects[group] = [value[0]]

        visual_container_objects = visual.get("visualContainerObjects", {})
        if isinstance(visual_container_objects, dict):
            for group, value in visual_container_objects.items():
                container_group_counts[group] += 1
                if group not in container_objects and isinstance(value, list) and value:
                    container_objects[group] = [value[0]]

    return {
        "objects": objects,
        "visualContainerObjects": container_objects,
        "object_group_counts": dict(sorted(object_group_counts.items())),
        "visual_container_group_counts": dict(sorted(container_group_counts.items())),
    }


def _role_examples_from_examples(examples: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}
    for example in examples:
        for binding in example["bindings"]:
            role = binding.get("role")
            if not role:
                continue
            role_entry = roles.setdefault(
                role,
                {
                    "visual_count": 0,
                    "projection_count": 0,
                    "sample_bindings": [],
                },
            )
            role_entry["projection_count"] += 1
            if len(role_entry["sample_bindings"]) < 5:
                role_entry["sample_bindings"].append(binding)

    for role, role_entry in roles.items():
        role_entry["visual_count"] = sum(
            1 for example in examples if role in example["query_roles"]
        )
    return dict(sorted(roles.items()))


def _serialize_visual_example(
    *,
    page_id: str,
    page_name: str,
    visual_id: str,
    visual_path: Path,
    visual_data: dict[str, Any],
) -> dict[str, Any]:
    visual = visual_data.get("visual", {})
    bindings = _extract_query_state_bindings(visual_data)
    example = {
        "page_id": page_id,
        "page_name": page_name,
        "visual_id": visual_id,
        "visual_type": visual.get("visualType", "unknown"),
        "title": _extract_visual_title(visual_data),
        "path": str(visual_path),
        "layout": _layout_from_visual(visual_data),
        "query_roles": _query_roles(bindings),
        "bindings": bindings,
        "object_groups": _object_groups(visual),
        "has_sort": bool(visual.get("query", {}).get("sortDefinition")),
        "has_filters": _has_filters(visual_data),
    }
    example["template_score"] = _score_template(example)
    return example


def _mine_examples(project_path: str) -> list[dict[str, Any]] | dict[str, str]:
    pages_dir = get_project_summary_paths(project_path).pages_dir
    if pages_dir is None or not pages_dir.exists():
        return {"error": f"Pages directory not found in {project_path}"}

    examples: list[dict[str, Any]] = []
    for page_id in _list_page_ids(pages_dir):
        page_dir = pages_dir / page_id
        page_name = _page_name(page_dir / "page.json")
        visuals_dir = page_dir / "visuals"
        if not visuals_dir.exists():
            continue

        for visual_dir in sorted(candidate for candidate in visuals_dir.iterdir() if candidate.is_dir()):
            visual_json = visual_dir / "visual.json"
            if not visual_json.exists():
                continue

            visual_data = _read_json(visual_json)
            examples.append(
                _serialize_visual_example(
                    page_id=page_id,
                    page_name=page_name,
                    visual_id=visual_dir.name,
                    visual_path=visual_json,
                    visual_data=visual_data,
                )
            )

    return examples


def visual_examples_list(
    project_path: str,
    visual_type: str | None = None,
    supported_only: bool = False,
    max_examples_per_type: int | None = 3,
) -> dict[str, Any]:
    mined = _mine_examples(project_path)
    if isinstance(mined, dict):
        return mined

    examples = mined
    if visual_type is not None:
        examples = [example for example in examples if example["visual_type"] == visual_type]
    if supported_only:
        examples = [example for example in examples if example["visual_type"] in SUPPORTED_VISUALS]

    total_matches = len(examples)
    type_counts: dict[str, int] = {}
    limited: list[dict[str, Any]] = []
    for example in sorted(examples, key=lambda item: (item["visual_type"], -item["template_score"], item["visual_id"])):
        current_count = type_counts.get(example["visual_type"], 0)
        if max_examples_per_type is None or current_count < max_examples_per_type:
            limited.append(example)
            type_counts[example["visual_type"]] = current_count + 1
        elif example["visual_type"] not in type_counts:
            type_counts[example["visual_type"]] = current_count

    all_type_counts: dict[str, int] = {}
    for example in examples:
        visual_key = example["visual_type"]
        all_type_counts[visual_key] = all_type_counts.get(visual_key, 0) + 1

    return {
        "visual_type": visual_type,
        "supported_only": supported_only,
        "max_examples_per_type": max_examples_per_type,
        "examples": limited,
        "total_matches": total_matches,
        "returned_count": len(limited),
        "type_counts": all_type_counts,
        "type_count": len(all_type_counts),
    }


def visual_template_recommend(project_path: str, visual_type: str) -> dict[str, Any]:
    result = visual_examples_list(
        project_path,
        visual_type=visual_type,
        supported_only=False,
        max_examples_per_type=None,
    )
    if "error" in result:
        return result

    examples = result["examples"]
    if not examples:
        return {
            "visual_type": visual_type,
            "found": False,
            "template": None,
            "reason": "No local PBIR example found for this visual type.",
        }

    template = sorted(
        examples,
        key=lambda item: (-item["template_score"], -len(item["bindings"]), item["visual_id"]),
    )[0]
    return {
        "visual_type": visual_type,
        "found": True,
        "template": template,
        "candidate_count": len(examples),
    }


def visual_role_examples(project_path: str, visual_type: str | None = None) -> dict[str, Any]:
    result = visual_examples_list(
        project_path,
        visual_type=visual_type,
        supported_only=False,
        max_examples_per_type=None,
    )
    if "error" in result:
        return result

    examples = result["examples"]
    roles = _role_examples_from_examples(examples)
    return {
        "project_path": project_path,
        "visual_type": visual_type,
        "visual_count": len(examples),
        "roles": roles,
        "role_count": len(roles),
    }


def visual_template_library(
    project_path: str,
    supported_only: bool = False,
    max_templates_per_type: int = 1,
) -> dict[str, Any]:
    result = visual_examples_list(
        project_path,
        visual_type=None,
        supported_only=supported_only,
        max_examples_per_type=None,
    )
    if "error" in result:
        return result

    examples = result["examples"]
    examples_by_type: dict[str, list[dict[str, Any]]] = {}
    for example in examples:
        examples_by_type.setdefault(example["visual_type"], []).append(example)

    templates_by_type: dict[str, list[dict[str, Any]]] = {}
    role_examples: dict[str, dict[str, Any]] = {}
    style_defaults: dict[str, dict[str, Any]] = {}
    for visual_type, visual_examples in sorted(examples_by_type.items()):
        sorted_examples = sorted(
            visual_examples,
            key=lambda item: (-item["template_score"], -len(item["bindings"]), item["visual_id"]),
        )
        templates_by_type[visual_type] = sorted_examples[:max_templates_per_type]
        role_examples[visual_type] = _role_examples_from_examples(visual_examples)
        style_defaults[visual_type] = _compact_style_defaults(visual_examples)

    return {
        "project_path": project_path,
        "supported_only": supported_only,
        "max_templates_per_type": max_templates_per_type,
        "visual_count": len(examples),
        "visual_type_count": len(templates_by_type),
        "templates_by_type": templates_by_type,
        "role_examples": role_examples,
        "style_defaults": style_defaults,
    }


def custom_visual_eligibility(project_path: str) -> dict[str, Any]:
    report_dir = get_project_summary_paths(project_path).report_dir
    if report_dir is None:
        return {"error": f"Report directory not found in {project_path}"}

    custom_visuals_dir = report_dir / "CustomVisuals"
    if not custom_visuals_dir.exists():
        return {
            "project_path": project_path,
            "custom_visuals": [],
            "count": 0,
            "guidance": "No CustomVisuals directory found; use native PBIR visuals only.",
        }

    fallback_by_name = {
        "textfilter": "slicer",
        "wordcloud": "barChart",
        "calendarvisual": "tableEx",
    }
    custom_visuals: list[dict[str, Any]] = []
    for package_path in sorted(custom_visuals_dir.glob("*/package.json")):
        package_data = _read_json(package_path)
        visual = package_data.get("visual", {})
        name = visual.get("name") or package_path.parent.name
        lowered_name = str(name).lower()
        custom_visuals.append(
            {
                "folder": package_path.parent.name,
                "guid": visual.get("guid"),
                "name": name,
                "displayName": visual.get("displayName"),
                "version": visual.get("version") or package_data.get("version"),
                "description": visual.get("description"),
                "supportUrl": visual.get("supportUrl"),
                "gitHubUrl": visual.get("gitHubUrl"),
                "can_generate_native_pbir": False,
                "eligibility": "detect-only",
                "recommended_native_fallback": fallback_by_name.get(lowered_name, "tableEx"),
                "reason": (
                    "Custom visual generation requires the packaged visual and its visual-specific "
                    "capabilities; use native fallback unless a custom-visual compiler is added."
                ),
            }
        )

    return {
        "project_path": project_path,
        "custom_visuals": custom_visuals,
        "count": len(custom_visuals),
        "guidance": "Detected custom visuals are eligible for analysis and fallback recommendation only.",
    }

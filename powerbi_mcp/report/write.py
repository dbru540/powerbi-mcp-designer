import shutil
import uuid
from pathlib import Path
from typing import Any

from powerbi_mcp.common.backups import backup_file, restore_from_backup
from powerbi_mcp.common.io import read_json, write_json_atomic
from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.validation.engine import pre_validate_payload, post_validate_paths
from powerbi_mcp.validation.report import ValidationReport


def _generate_id() -> str:
    return uuid.uuid4().hex[:20]


def _get_pages_dir(project_path: str) -> Path | None:
    return get_project_summary_paths(project_path).pages_dir


def _get_visual_path(project_path: str, page_id: str, visual_id: str) -> Path:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        raise FileNotFoundError("Pages directory not found")
    return pages_dir / page_id / "visuals" / visual_id / "visual.json"


def _get_page_path(project_path: str, page_id: str) -> Path:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        raise FileNotFoundError("Pages directory not found")
    return pages_dir / page_id / "page.json"


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _literal_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _literal_expr(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def _solid_literal_color(value: str) -> dict[str, Any]:
    return {"solid": {"color": _literal_expr(_literal_string(value))}}


def _field_type_for_binding(binding: dict[str, Any]) -> str:
    field_type = binding.get("field_type")
    if isinstance(field_type, str) and field_type:
        return field_type

    kind = str(binding.get("kind") or "").lower()
    if kind in {"measure", "value", "metric"}:
        return "Measure"
    if kind == "aggregation":
        return "Aggregation"
    return "Column"


def _projection_for_binding(binding: dict[str, Any]) -> dict[str, Any]:
    entity = binding.get("entity")
    property_name = binding.get("property")
    field_type = _field_type_for_binding(binding)
    projection = {
        "field": {
            field_type: {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": property_name,
            }
        },
        "queryRef": binding.get("query_ref") or f"{entity}.{property_name}",
        "nativeQueryRef": binding.get("native_query_ref") or property_name,
    }
    if binding.get("display_name"):
        projection["displayName"] = binding["display_name"]
    return projection


def _query_state_from_role_assignments(
    role_assignments: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    query_state: dict[str, Any] = {}
    for role, bindings in role_assignments.items():
        projections = [
            _projection_for_binding(binding)
            for binding in bindings
            if binding.get("entity") and binding.get("property")
        ]
        if projections:
            query_state[role] = {"projections": projections}
    return query_state


def _legacy_role_assignments(
    visual_type: str,
    category_entity: str | None,
    category_property: str | None,
    measure_entity: str | None,
    measure_property: str | None,
) -> dict[str, list[dict[str, Any]]]:
    category = (
        {"kind": "dimension", "entity": category_entity, "property": category_property}
        if category_entity and category_property
        else None
    )
    measure = (
        {"kind": "measure", "entity": measure_entity, "property": measure_property}
        if measure_entity and measure_property
        else None
    )

    if visual_type == "card":
        return {"Values": [measure] if measure else []}
    if visual_type == "slicer":
        return {"Values": [category] if category else []}
    if visual_type == "tableEx":
        return {"Values": [item for item in (category, measure) if item]}
    if visual_type == "pivotTable":
        return {
            "Rows": [category] if category else [],
            "Values": [measure] if measure else [],
        }
    return {
        "Category": [category] if category else [],
        "Y": [measure] if measure else [],
    }


def _presentation_visual_defaults(visual_type: str, title: str | None) -> dict[str, Any]:
    if visual_type == "card":
        return {
            "objects": {
                "labels": [{"properties": {"fontSize": _literal_expr("22D")}}],
                "categoryLabels": [{"properties": {"show": _literal_expr("false")}}],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal_expr("false")}}],
                "dropShadow": [{"properties": {"show": _literal_expr("false")}}],
                "border": [{"properties": {"show": _literal_expr("false")}}],
                "background": [
                    {
                        "properties": {
                            "show": _literal_expr("false"),
                            "transparency": _literal_expr("0D"),
                        }
                    }
                ],
            },
        }
    if visual_type in {
        "barChart",
        "clusteredBarChart",
        "columnChart",
        "clusteredColumnChart",
        "lineChart",
    }:
        objects: dict[str, Any] = {
            "labels": [{"properties": {"show": _literal_expr("true")}}],
            "categoryAxis": [{"properties": {"showAxisTitle": _literal_expr("false")}}],
            "valueAxis": [
                {
                    "properties": {
                        "gridlineShow": _literal_expr("true"),
                        "showAxisTitle": _literal_expr("false"),
                    }
                }
            ],
        }
        if visual_type in {"lineChart", "columnChart", "clusteredColumnChart"}:
            objects["legend"] = [{"properties": {"show": _literal_expr("true")}}]
        return {
            "objects": objects,
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal_expr("false")}}],
                "visualTooltip": [{"properties": {"show": _literal_expr("true")}}],
            },
        }
    if visual_type in {"pieChart", "donutChart"}:
        return {
            "objects": {
                "labels": [{"properties": {"labelStyle": _literal_expr("'Data'")}}],
                "legend": [
                    {
                        "properties": {
                            "show": _literal_expr("true"),
                            "position": _literal_expr("'Top'"),
                            "showTitle": _literal_expr("false"),
                        }
                    }
                ],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal_expr("false")}}],
                "visualTooltip": [{"properties": {"show": _literal_expr("true")}}],
            },
        }
    if visual_type in {"tableEx", "pivotTable"}:
        objects = {
            "values": [
                {
                    "properties": {
                        "backColorSecondary": _solid_literal_color("#F9F4FA"),
                    }
                }
            ],
            "columnHeaders": [{"properties": {"fontSize": _literal_expr("9D")}}],
            "grid": [
                {
                    "properties": {
                        "outlineColor": _solid_literal_color("#D9DEE5"),
                        "gridVertical": _literal_expr("false"),
                    }
                }
            ],
            "columnWidth": [{"properties": {}}],
        }
        if visual_type == "pivotTable":
            objects.update(
                {
                    "rowHeaders": [{"properties": {"fontSize": _literal_expr("9D")}}],
                    "subTotals": [{"properties": {"rowSubtotals": _literal_expr("true")}}],
                    "total": [{"properties": {"totals": _literal_expr("true")}}],
                    "blankRows": [{"properties": {"show": _literal_expr("false")}}],
                }
            )
        else:
            objects["total"] = [{"properties": {"totals": _literal_expr("true")}}]
        return {
            "objects": objects,
            "visualContainerObjects": {
                "general": [{"properties": {}}],
                "visualHeader": [{"properties": {"show": _literal_expr("false")}}],
                "visualTooltip": [{"properties": {"show": _literal_expr("true")}}],
            },
        }
    if visual_type == "shape":
        return {
            "objects": {
                "shape": [{"properties": {"tileShape": {"expr": {"Literal": {"Value": "'rectangle'"}}}}}],
                "fill": [
                    {
                        "properties": {
                            "fillColor": {
                                "solid": {"color": {"expr": {"Literal": {"Value": "'#F3F5F7'"}}}}
                            }
                        },
                        "selector": {"id": "default"},
                    }
                ],
                "outline": [
                    {
                        "properties": {
                            "lineColor": {
                                "solid": {"color": {"expr": {"Literal": {"Value": "'#D9DEE5'"}}}}
                            },
                            "weight": {"expr": {"Literal": {"Value": "1D"}}},
                        },
                        "selector": {"id": "default"},
                    }
                ],
            }
        }
    if visual_type == "textbox":
        text = title or "Narrative"
        return {
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": text,
                                            "textStyle": {"fontWeight": "bold"},
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }
        }
    if visual_type == "image":
        return {
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
            }
        }
    if visual_type == "slicer":
        return {
            "objects": {
                "data": [
                    {
                        "properties": {
                            "mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}},
                        }
                    }
                ],
                "header": [{"properties": {"show": _literal_expr("false")}}],
                "general": [{"properties": {}}],
                "selection": [
                    {"properties": {"strictSingleSelect": _literal_expr("false")}}
                ],
            },
            "visualContainerObjects": {
                "visualHeader": [{"properties": {"show": _literal_expr("false")}}],
                "border": [{"properties": {"show": _literal_expr("true")}}],
                "dropShadow": [{"properties": {"show": _literal_expr("true")}}],
            },
        }
    return {}


def _validate_pre(payload: dict, file_path: str) -> ValidationReport | None:
    """Returns ValidationReport if pre-validation fails, else None."""
    report = pre_validate_payload(payload, file_path)
    if report.has_errors():
        return report
    return None


def _validate_post(
    project_path: str,
    backup_pairs: list[tuple[str, str | None]],
    touched_new_paths: list[str],
) -> ValidationReport | None:
    """Returns ValidationReport if post-validation fails (and restores backups), else None."""
    touched = [orig for orig, _ in backup_pairs] + touched_new_paths
    report = post_validate_paths(project_path, touched)
    if report.has_errors():
        for orig, bak in backup_pairs:
            if bak is not None:
                restore_from_backup(orig, bak)
        return report
    return None


def report_create_page(
    project_path: str,
    display_name: str,
    width: int = 1280,
    height: int = 720,
    dry_run: bool = False,
) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None or not pages_dir.exists():
        return {"error": "Pages directory not found"}

    page_id = _generate_id()
    page_path = pages_dir / page_id
    meta_path = pages_dir / "pages.json"
    if not meta_path.exists():
        return {"error": "pages.json not found"}

    meta = read_json(meta_path)
    meta.setdefault("pageOrder", []).append(page_id)

    page_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": height,
        "width": width,
    }

    # Pre-validate the new page payload
    fail = _validate_pre(page_config, str(page_path / "page.json"))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "page_id": page_id,
            "path": str(page_path),
            "displayName": display_name,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    page_path.mkdir(parents=True, exist_ok=False)
    (page_path / "visuals").mkdir(exist_ok=True)
    write_json_atomic(page_path / "page.json", page_config)
    meta_bak = backup_file(meta_path)
    write_json_atomic(meta_path, meta)

    fail = _validate_post(
        project_path,
        [(str(meta_path), meta_bak)],
        [str(page_path / "page.json")],
    )
    if fail is not None:
        shutil.rmtree(str(page_path), ignore_errors=True)
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "page_id": page_id,
        "path": str(page_path),
        "displayName": display_name,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_create_visual(
    project_path: str,
    page_id: str,
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str | None = None,
    category_entity: str | None = None,
    category_property: str | None = None,
    measure_entity: str | None = None,
    measure_property: str | None = None,
    role_assignments: dict[str, list[dict[str, Any]]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = _generate_id()
    visual_dir = visuals_dir / visual_id
    visual_config: dict[str, Any] = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x,
            "y": y,
            "z": 0,
            "width": width,
            "height": height,
        },
        "visual": {
            "visualType": visual_type,
        },
    }

    visual_defaults = _presentation_visual_defaults(visual_type, title)
    if visual_defaults:
        visual_config["visual"] = _deep_merge(visual_config["visual"], visual_defaults)

    if role_assignments is None:
        role_assignments = _legacy_role_assignments(
            visual_type,
            category_entity,
            category_property,
            measure_entity,
            measure_property,
        )

    query_state = _query_state_from_role_assignments(role_assignments)
    if query_state:
        visual_config["visual"]["query"] = {"queryState": query_state}

    if title and visual_type != "textbox":
        container_objects = visual_config["visual"].setdefault("visualContainerObjects", {})
        container_objects["title"] = [
            {
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": _literal_string(title)}}},
                }
            }
        ]

    # Pre-validate the new visual payload
    fail = _validate_pre(visual_config, str(visual_dir / "visual.json"))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "path": str(visual_dir),
            "visualType": visual_type,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    visual_dir.mkdir(parents=True, exist_ok=False)
    new_visual_path = visual_dir / "visual.json"
    write_json_atomic(new_visual_path, visual_config)

    fail = _validate_post(project_path, [], [str(new_visual_path)])
    if fail is not None:
        shutil.rmtree(str(visual_dir), ignore_errors=True)
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "path": str(visual_dir),
        "visualType": visual_type,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_create_deneb_visual(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    vega_lite_spec: Any,
    dataset_bindings: list[dict[str, Any]],
    title: str | None = None,
    vega_lite_config: Any = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    import json
    pages_dir = _get_pages_dir(project_path)
    if pages_dir is None:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = _generate_id()
    visual_dir = visuals_dir / visual_id
    
    # Process vega-lite specification
    if isinstance(vega_lite_spec, dict):
        json_spec_str = json.dumps(vega_lite_spec)
    else:
        json_spec_str = str(vega_lite_spec)

    # Process vega-lite config
    if vega_lite_config is None:
        json_config_str = "{}"
    elif isinstance(vega_lite_config, dict):
        json_config_str = json.dumps(vega_lite_config)
    else:
        json_config_str = str(vega_lite_config)

    visual_config: dict[str, Any] = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x,
            "y": y,
            "z": 0,
            "width": width,
            "height": height,
        },
        "visual": {
            "visualType": "deneb7E15AEF80B9E4D4F8E12924291ECE89A",
            "objects": {
                "vega": [
                    {
                        "properties": {
                            "jsonSpec": {
                                "expr": {
                                    "Literal": {
                                        "Value": _literal_string(json_spec_str)
                                    }
                                }
                            },
                            "jsonConfig": {
                                "expr": {
                                    "Literal": {
                                        "Value": _literal_string(json_config_str)
                                    }
                                }
                            }
                        }
                    }
                ],
                "developer": [
                    {
                        "properties": {
                            "provider": {
                                "expr": {
                                    "Literal": {
                                        "Value": "'vegaLite'"
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        },
    }

    # Deneb expects queryState role named "dataset"
    role_assignments = {"dataset": dataset_bindings}
    query_state = _query_state_from_role_assignments(role_assignments)
    if query_state:
        visual_config["visual"]["query"] = {"queryState": query_state}

    if title:
        visual_config["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": _literal_string(title)}}},
                }
            }]
        }

    # Pre-validate the new visual payload
    fail = _validate_pre(visual_config, str(visual_dir / "visual.json"))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "path": str(visual_dir),
            "visualType": "deneb7E15AEF80B9E4D4F8E12924291ECE89A",
            "validation": ValidationReport.ok_report().to_dict(),
        }

    visual_dir.mkdir(parents=True, exist_ok=False)
    new_visual_path = visual_dir / "visual.json"
    write_json_atomic(new_visual_path, visual_config)

    fail = _validate_post(project_path, [], [str(new_visual_path)])
    if fail is not None:
        shutil.rmtree(str(visual_dir), ignore_errors=True)
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "path": str(visual_dir),
        "visualType": "deneb7E15AEF80B9E4D4F8E12924291ECE89A",
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_move_visual(
    project_path: str,
    page_id: str,
    visual_id: str,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        visual_path = _get_visual_path(project_path, page_id, visual_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}

    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    visual_data = read_json(visual_path)
    position = dict(visual_data.get("position", {}))
    if x is not None:
        position["x"] = x
    if y is not None:
        position["y"] = y
    if width is not None:
        position["width"] = width
    if height is not None:
        position["height"] = height
    visual_data["position"] = position

    fail = _validate_pre(visual_data, str(visual_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "new_position": position,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(visual_path)
    write_json_atomic(visual_path, visual_data)

    fail = _validate_post(project_path, [(str(visual_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "new_position": position,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_update_visual_json(
    project_path: str,
    page_id: str,
    visual_id: str,
    json_patch: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        visual_path = _get_visual_path(project_path, page_id, visual_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    visual_data = read_json(visual_path)
    visual_data = _deep_merge(visual_data, json_patch)

    fail = _validate_pre(visual_data, str(visual_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "patched": True,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(visual_path)
    write_json_atomic(visual_path, visual_data)

    fail = _validate_post(project_path, [(str(visual_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "patched": True,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_extract_visual_config(
    project_path: str,
    page_id: str,
    visual_id: str,
    include_query: bool = False,
    include_position: bool = False,
) -> dict[str, Any]:
    try:
        visual_path = _get_visual_path(project_path, page_id, visual_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    visual_data = read_json(visual_path)
    config = {
        "visualType": visual_data.get("visual", {}).get("visualType"),
        "objects": visual_data.get("visual", {}).get("objects", {}),
        "visualContainerObjects": visual_data.get("visual", {}).get("visualContainerObjects", {}),
        "vcObjects": visual_data.get("visual", {}).get("vcObjects", {}),
    }
    if include_query:
        config["query"] = visual_data.get("visual", {}).get("query", {})
    if include_position:
        config["position"] = visual_data.get("position", {})

    return {"visual_id": visual_id, "config": config}


def report_apply_visual_style(
    project_path: str,
    page_id: str,
    visual_id: str,
    style_config: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        visual_path = _get_visual_path(project_path, page_id, visual_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    visual_data = read_json(visual_path)
    visual_data.setdefault("visual", {})
    if "objects" in style_config:
        visual_data["visual"]["objects"] = style_config["objects"]
    if "visualContainerObjects" in style_config:
        visual_data["visual"]["visualContainerObjects"] = style_config["visualContainerObjects"]
    if "vcObjects" in style_config:
        visual_data["visual"]["vcObjects"] = style_config["vcObjects"]

    fail = _validate_pre(visual_data, str(visual_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "style_applied": True,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(visual_path)
    write_json_atomic(visual_path, visual_data)

    fail = _validate_post(project_path, [(str(visual_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "style_applied": True,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_clone_visual_style(
    project_path: str,
    source_page_id: str,
    source_visual_id: str,
    target_page_id: str,
    target_visual_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_config = report_extract_visual_config(
        project_path,
        source_page_id,
        source_visual_id,
        include_query=False,
        include_position=False,
    )
    if "error" in source_config:
        return source_config

    return report_apply_visual_style(
        project_path,
        target_page_id,
        target_visual_id,
        source_config["config"],
        dry_run=dry_run,
    )


def report_update_visual_title(
    project_path: str,
    page_id: str,
    visual_id: str,
    title: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        visual_path = _get_visual_path(project_path, page_id, visual_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    visual_data = read_json(visual_path)
    visual_data.setdefault("visual", {})
    visual_data["visual"].setdefault("visualContainerObjects", {})
    visual_data["visual"]["visualContainerObjects"]["title"] = [{
        "properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
        }
    }]

    fail = _validate_pre(visual_data, str(visual_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "visual_id": visual_id,
            "new_title": title,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(visual_path)
    write_json_atomic(visual_path, visual_data)

    fail = _validate_post(project_path, [(str(visual_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "visual_id": visual_id,
        "new_title": title,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_update_page_size(
    project_path: str,
    page_id: str,
    width: int | None = None,
    height: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        page_path = _get_page_path(project_path, page_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not page_path.exists():
        return {"error": f"Page not found: {page_id}"}

    page_data = read_json(page_path)
    if width is not None:
        page_data["width"] = width
    if height is not None:
        page_data["height"] = height

    fail = _validate_pre(page_data, str(page_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "page_id": page_id,
            "width": page_data.get("width"),
            "height": page_data.get("height"),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(page_path)
    write_json_atomic(page_path, page_data)

    fail = _validate_post(project_path, [(str(page_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "page_id": page_id,
        "width": page_data.get("width"),
        "height": page_data.get("height"),
        "validation": ValidationReport.ok_report().to_dict(),
    }


def report_rename_page(
    project_path: str,
    page_id: str,
    new_name: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        page_path = _get_page_path(project_path, page_id)
    except FileNotFoundError:
        return {"error": "Pages directory not found"}
    if not page_path.exists():
        return {"error": f"Page not found: {page_id}"}

    page_data = read_json(page_path)
    old_name = page_data.get("displayName", "")
    page_data["displayName"] = new_name

    fail = _validate_pre(page_data, str(page_path))
    if fail is not None:
        return {"success": False, "error": "pre-validation failed", "validation": fail.to_dict()}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "page_id": page_id,
            "old_name": old_name,
            "new_name": new_name,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    bak = backup_file(page_path)
    write_json_atomic(page_path, page_data)

    fail = _validate_post(project_path, [(str(page_path), bak)], [])
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "page_id": page_id,
        "old_name": old_name,
        "new_name": new_name,
        "validation": ValidationReport.ok_report().to_dict(),
    }

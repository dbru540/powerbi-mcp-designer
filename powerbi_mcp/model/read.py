import json
import re
from pathlib import Path
from typing import Any

from powerbi_mcp.common.paths import get_project_summary_paths


_MEASURE_PROPERTY_HEADER_RE = re.compile(
    r"^\t\t(?:(?P<property>[A-Za-z][A-Za-z0-9]*)\s*(?::|=)|(?P<keyword>annotation|changedProperty|extendedProperty)\b)"
)
_MEASURE_HEADER_RE = re.compile(r"^\tmeasure\s+(?P<name>'.+?'|[^\n=]+?)\s*=\s*(?P<inline>.*)$")
_RELATIONSHIP_HEADER_RE = re.compile(r"^relationship\s+(?P<name>'.+?'|[^\n]+?)$")
_FIELD_REF_RE = re.compile(
    r"^(?P<table>'[^']+'|[^.]+)\.(?P<column>'[^']+'|.+)$"
)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _is_exactly_tab_indented(line: str, level: int) -> bool:
    prefix = "\t" * level
    return line.startswith(prefix) and not line.startswith(f"{prefix}\t")


def _match_measure_property_header(line: str) -> re.Match[str] | None:
    if not _is_exactly_tab_indented(line, 2):
        return None

    return _MEASURE_PROPERTY_HEADER_RE.match(line)


def _get_definition_dir(project_path: str) -> Path | None:
    model_dir = get_project_summary_paths(project_path).model_dir
    if model_dir is None:
        return None

    return model_dir / "definition"


def _get_model_bim_path(project_path: str) -> Path | None:
    model_dir = get_project_summary_paths(project_path).model_dir
    if model_dir is None:
        return None

    return model_dir / "model.bim"


def _get_tables_dir(project_path: str) -> Path | None:
    return get_project_summary_paths(project_path).tables_dir


def _list_table_files(project_path: str) -> tuple[Path | None, dict[str, Any] | None, list[Path]]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is None:
        return None, {"error": "SemanticModel directory not found"}, []
    if not tables_dir.exists():
        return tables_dir, {"error": "Tables directory not found"}, []

    return tables_dir, None, sorted(tables_dir.glob("*.tmdl"))


def _load_bim_model(project_path: str) -> tuple[Path | None, dict[str, Any] | None, dict[str, Any] | None]:
    model_bim = _get_model_bim_path(project_path)
    if model_bim is None:
        return None, None, {"error": "SemanticModel directory not found"}
    if not model_bim.exists():
        return model_bim, None, {"error": "model.bim not found"}

    return model_bim, _read_json(model_bim).get("model", {}), None


def _normalize_bim_expression(expression: Any) -> str:
    if isinstance(expression, list):
        return "\n".join(str(line) for line in expression).strip()
    if expression is None:
        return ""
    return str(expression).strip()


def _parse_model_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"^\t{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        return None

    return match.group(1).strip()


def _parse_model_refs(text: str, kind: str) -> list[str]:
    pattern = re.compile(rf"^ref {re.escape(kind)}\s+(.+)$", flags=re.MULTILINE)
    return [_strip_quotes(match.group(1)) for match in pattern.finditer(text)]


def _parse_measure_blocks(table_name: str, table_path: Path) -> list[dict[str, Any]]:
    lines = _read_text(table_path).splitlines()
    measures: list[dict[str, Any]] = []
    index = 0

    while index < len(lines):
        header_match = _MEASURE_HEADER_RE.match(lines[index])
        if header_match is None:
            index += 1
            continue

        name = _strip_quotes(header_match.group("name"))
        block_lines: list[str] = []
        inline_expression = header_match.group("inline").rstrip()
        if inline_expression:
            block_lines.append(inline_expression)

        display_folder: str | None = None
        in_property_section = False
        index += 1

        while index < len(lines):
            line = lines[index]
            if _is_exactly_tab_indented(line, 1):
                break

            property_match = _match_measure_property_header(line)
            if property_match is not None:
                if property_match.group("property") == "displayFolder":
                    display_folder = line.split(":", 1)[1].strip()
                in_property_section = True
                index += 1
                continue

            if in_property_section:
                index += 1
                continue

            block_lines.append(line)
            index += 1

        expression = "\n".join(block_lines).strip()
        if expression.startswith("```") and expression.endswith("```"):
            expression = expression[3:-3].strip()

        measures.append(
            {
                "table": table_name,
                "name": name,
                "expression": expression,
                "display_folder": display_folder,
                "path": str(table_path),
            }
        )

    return measures


def _parse_relationship_field(value: str) -> tuple[str, str]:
    match = _FIELD_REF_RE.match(value.strip())
    if match is None:
        return value.strip(), ""

    return (
        _strip_quotes(match.group("table")),
        _strip_quotes(match.group("column")),
    )


def get_table_content(project_path: str, table_name: str) -> dict[str, Any]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is not None and tables_dir.exists():
        table_path = tables_dir / f"{table_name}.tmdl"
        if table_path.exists():
            return {
                "table_name": table_name,
                "content": _read_text(table_path),
                "path": str(table_path),
            }

    model_bim, model, error = _load_bim_model(project_path)
    if error is not None:
        if tables_dir is not None and not tables_dir.exists():
            return {"error": "Tables directory not found"}
        return error

    for table in model.get("tables", []):
        if table.get("name") == table_name:
            return {
                "table_name": table_name,
                "content": json.dumps(table, ensure_ascii=False, indent=2),
                "path": str(model_bim),
            }

    return {"error": f"Table not found: {table_name}"}


def model_list_tables(project_path: str) -> dict[str, Any]:
    _tables_dir, error, table_files = _list_table_files(project_path)
    if error is None:
        tables = [{"name": table_file.stem, "path": str(table_file)} for table_file in table_files]
        return {"tables": tables, "count": len(tables)}

    model_bim, model, bim_error = _load_bim_model(project_path)
    if bim_error is not None:
        return error

    tables = [
        {"name": table.get("name", ""), "path": str(model_bim)}
        for table in model.get("tables", [])
        if isinstance(table.get("name"), str)
    ]
    return {"tables": tables, "count": len(tables)}


def model_list_relationships(project_path: str) -> dict[str, Any]:
    definition_dir = _get_definition_dir(project_path)
    if definition_dir is None:
        return {"error": "SemanticModel directory not found"}

    relationships_path = definition_dir / "relationships.tmdl"
    if not relationships_path.exists():
        model_bim, model, error = _load_bim_model(project_path)
        if error is not None:
            return {"error": "relationships.tmdl not found"}

        relationships = []
        for relationship in model.get("relationships", []):
            relationships.append(
                {
                    "name": relationship.get("name"),
                    "from_table": relationship.get("fromTable"),
                    "from_column": relationship.get("fromColumn"),
                    "to_table": relationship.get("toTable"),
                    "to_column": relationship.get("toColumn"),
                    "is_active": relationship.get("isActive", True),
                    "cross_filtering_behavior": relationship.get("crossFilteringBehavior"),
                    "from_cardinality": relationship.get("fromCardinality"),
                    "path": str(model_bim),
                }
            )

        return {"relationships": relationships, "count": len(relationships)}

    lines = _read_text(relationships_path).splitlines()
    relationships: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in lines:
        header_match = _RELATIONSHIP_HEADER_RE.match(line)
        if header_match is not None:
            if current is not None:
                relationships.append(current)

            current = {
                "name": _strip_quotes(header_match.group("name")),
                "from_table": None,
                "from_column": None,
                "to_table": None,
                "to_column": None,
                "is_active": True,
                "cross_filtering_behavior": None,
                "from_cardinality": None,
                "path": str(relationships_path),
            }
            continue

        if current is None or not line.startswith("\t"):
            continue

        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue

        key, raw_value = stripped.split(":", 1)
        value = raw_value.strip()

        if key == "fromColumn":
            current["from_table"], current["from_column"] = _parse_relationship_field(value)
        elif key == "toColumn":
            current["to_table"], current["to_column"] = _parse_relationship_field(value)
        elif key == "isActive":
            current["is_active"] = value.lower() != "false"
        elif key == "crossFilteringBehavior":
            current["cross_filtering_behavior"] = value
        elif key == "fromCardinality":
            current["from_cardinality"] = value

    if current is not None:
        relationships.append(current)

    return {"relationships": relationships, "count": len(relationships)}


def model_list_measures(project_path: str) -> dict[str, Any]:
    _tables_dir, error, table_files = _list_table_files(project_path)
    if error is None:
        measures: list[dict[str, Any]] = []
        for table_file in table_files:
            measures.extend(_parse_measure_blocks(table_file.stem, table_file))

        return {"measures": measures, "count": len(measures)}

    model_bim, model, bim_error = _load_bim_model(project_path)
    if bim_error is not None:
        return error

    measures: list[dict[str, Any]] = []
    for table in model.get("tables", []):
        table_name = table.get("name")
        if not isinstance(table_name, str):
            continue
        for measure in table.get("measures", []):
            measure_name = measure.get("name")
            if not isinstance(measure_name, str):
                continue
            measures.append(
                {
                    "table": table_name,
                    "name": measure_name,
                    "expression": _normalize_bim_expression(measure.get("expression")),
                    "display_folder": measure.get("displayFolder"),
                    "path": str(model_bim),
                }
            )

    return {"measures": measures, "count": len(measures)}


def model_get_summary(project_path: str) -> dict[str, Any]:
    definition_dir = _get_definition_dir(project_path)
    if definition_dir is None:
        return {"error": "SemanticModel directory not found"}

    model_path = definition_dir / "model.tmdl"
    if not model_path.exists():
        model_bim, model, error = _load_bim_model(project_path)
        if error is not None:
            return {"error": "model.tmdl not found"}

        tables_result = model_list_tables(project_path)
        relationships_result = model_list_relationships(project_path)
        measures_result = model_list_measures(project_path)
        roles = [
            role.get("name")
            for role in model.get("roles", [])
            if isinstance(role.get("name"), str)
        ]
        tables = [table["name"] for table in tables_result["tables"]]

        return {
            "model_name": model.get("name"),
            "culture": model.get("culture"),
            "source_query_culture": model.get("sourceQueryCulture"),
            "table_count": tables_result["count"],
            "relationship_count": relationships_result["count"],
            "measure_count": measures_result["count"],
            "role_count": len(roles),
            "roles": roles,
            "tables": tables,
            "path": str(model_bim),
        }

    model_text = _read_text(model_path)
    tables_result = model_list_tables(project_path)
    if "error" in tables_result:
        return tables_result

    relationships_result = model_list_relationships(project_path)
    if "error" in relationships_result:
        return relationships_result

    measures_result = model_list_measures(project_path)
    if "error" in measures_result:
        return measures_result

    roles = _parse_model_refs(model_text, "role")
    tables = [table["name"] for table in tables_result["tables"]]

    model_name_match = re.search(r"^model\s+(.+)$", model_text, flags=re.MULTILINE)
    model_name = _strip_quotes(model_name_match.group(1)) if model_name_match else None

    return {
        "model_name": model_name,
        "culture": _parse_model_scalar(model_text, "culture"),
        "source_query_culture": _parse_model_scalar(model_text, "sourceQueryCulture"),
        "table_count": tables_result["count"],
        "relationship_count": relationships_result["count"],
        "measure_count": measures_result["count"],
        "role_count": len(roles),
        "roles": roles,
        "tables": tables,
        "path": str(model_path),
    }

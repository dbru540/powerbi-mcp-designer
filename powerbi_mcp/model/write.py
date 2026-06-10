from pathlib import Path
import uuid
import re
import json

from powerbi_mcp.common.backups import backup_file, restore_from_backup
from powerbi_mcp.common.paths import get_project_summary_paths, safe_child
from powerbi_mcp.model.read import _strip_quotes
from powerbi_mcp.validation.engine import post_validate_paths
from powerbi_mcp.validation.report import ValidationReport


def _validate_post_tmdl(project_path: str, tmdl_path: str, backup_path: str | None) -> ValidationReport | None:
    """Returns ValidationReport if post-validation fails (and restores backup), else None."""
    report = post_validate_paths(project_path, [tmdl_path])
    if report.has_errors():
        if backup_path is not None:
            restore_from_backup(tmdl_path, backup_path)
        return report
    return None


def _get_tables_dir(project_path: str) -> Path | None:
    return get_project_summary_paths(project_path).tables_dir


def _get_relationships_path(project_path: str) -> Path | None:
    model_dir = get_project_summary_paths(project_path).model_dir
    if model_dir is None:
        return None
    return model_dir / "definition" / "relationships.tmdl"


def _get_roles_dir(project_path: str) -> Path | None:
    model_dir = get_project_summary_paths(project_path).model_dir
    if model_dir is None:
        return None
    return model_dir / "definition" / "roles"


def _measure_header(table_name: str, measure_name: str, expression: str) -> str:
    escaped_name = measure_name if measure_name.startswith("'") and measure_name.endswith("'") else f"'{measure_name}'"
    return f"\tmeasure {escaped_name} = {expression}"


def _format_measure_block(measure_name: str, expression: str) -> list[str]:
    escaped_name = measure_name if measure_name.startswith("'") and measure_name.endswith("'") else f"'{measure_name}'"
    if "\n" not in expression:
        return [f"\tmeasure {escaped_name} = {expression}"]

    expression_lines = expression.splitlines()
    block = [f"\tmeasure {escaped_name} ="]
    block.extend(f"\t\t\t{line}" if line else "" for line in expression_lines)
    return block


def _find_measure_block(lines: list[str], measure_name: str) -> tuple[int | None, int | None]:
    normalized_name = measure_name.strip("'")
    start = None
    end = None
    for index, line in enumerate(lines):
        if not line.startswith("\tmeasure "):
            continue
        current_name = _strip_quotes(line[len("\tmeasure "):].split("=", 1)[0].strip())
        if current_name != normalized_name:
            continue
        start = index
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            if lines[cursor].startswith("\tmeasure ") or (
                lines[cursor].startswith("\t")
                and not lines[cursor].startswith("\t\t")
            ):
                end = cursor
                break
        break
    return start, end


def _is_exactly_tab_indented(line: str, level: int) -> bool:
    prefix = "\t" * level
    return line.startswith(prefix) and not line.startswith(f"{prefix}\t")


def _split_measure_block(block_lines: list[str]) -> tuple[list[str], list[str]]:
    expression_lines = [block_lines[0]]
    metadata_start = len(block_lines)

    for index in range(1, len(block_lines)):
        line = block_lines[index]
        if _is_exactly_tab_indented(line, 2):
            metadata_start = index
            break
        expression_lines.append(line)

    return expression_lines, block_lines[metadata_start:]


def _find_table_object_block(
    lines: list[str],
    object_prefix: str,
    object_name: str,
) -> tuple[int | None, int | None]:
    normalized_name = object_name.strip("'")
    start = None
    end = None

    for index, line in enumerate(lines):
        if not line.startswith(object_prefix):
            continue

        declaration = line[len(object_prefix):]
        if "=" in declaration:
            declaration = declaration.split("=", 1)[0]
        current_name = _strip_quotes(declaration.strip())
        if current_name != normalized_name:
            continue

        start = index
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            candidate = lines[cursor]
            if candidate.startswith("\tcolumn ") or candidate.startswith("\tmeasure ") or candidate.startswith("\tpartition "):
                end = cursor
                break
        break

    return start, end


def _find_top_level_object_insert_index(lines: list[str]) -> int:
    return next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("\tcolumn ") or line.startswith("\tmeasure ") or line.startswith("\tpartition ")
        ),
        len(lines),
    )


def model_upsert_measure(
    project_path: str,
    table_name: str,
    measure_name: str,
    expression: str,
    dry_run: bool = False,
) -> dict[str, object]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is None:
        return {"error": "SemanticModel directory not found"}
    if not tables_dir.exists():
        return {"error": "Tables directory not found"}

    table_path = safe_child(tables_dir, f"{table_name}.tmdl")
    if not table_path.exists():
        return {"error": f"Table not found: {table_name}"}

    lines = table_path.read_text(encoding="utf-8").splitlines()
    start, end = _find_measure_block(lines, measure_name)

    action = "created"
    new_lines = list(lines)
    if start is not None and end is not None:
        action = "updated"
        _old_expression_lines, metadata_lines = _split_measure_block(new_lines[start:end])
        replacement_block = _format_measure_block(measure_name, expression) + metadata_lines
        new_lines[start:end] = replacement_block
    else:
        insert_at = next(
            (
                index
                for index, line in enumerate(new_lines)
                if line.startswith("\tcolumn ") or line.startswith("\tpartition ")
            ),
            len(new_lines),
        )
        block = _format_measure_block(measure_name, expression) + [""]
        new_lines[insert_at:insert_at] = block

    new_text = "\n".join(new_lines).rstrip() + "\n"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "action": action,
            "table_path": str(table_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    backup = backup_file(table_path)
    table_path.write_text(new_text, encoding="utf-8")

    fail = _validate_post_tmdl(project_path, str(table_path), backup)
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "action": action,
        "table_path": str(table_path),
        "backup_file": backup,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def _relationship_header(relationship_name: str) -> str:
    return f"relationship {relationship_name}"


def _format_identifier(identifier: str) -> str:
    stripped = identifier.strip()
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped
    if stripped.replace("_", "").isalnum() and " " not in stripped and "-" not in stripped:
        return stripped
    return "'" + stripped.replace("'", "''") + "'"


def _format_field_ref(table_name: str, column_name: str) -> str:
    return f"{_format_identifier(table_name)}.{_format_identifier(column_name)}"


def _format_role_name(role_name: str) -> str:
    return _format_identifier(role_name)


def _relationship_lines(
    relationship_name: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> list[str]:
    return [
        _relationship_header(relationship_name),
        f"\tfromColumn: {_format_field_ref(from_table, from_column)}",
        f"\ttoColumn: {_format_field_ref(to_table, to_column)}",
        "",
    ]


def _find_relationship_block(lines: list[str], relationship_name: str) -> tuple[int | None, int | None]:
    start = None
    end = None
    target = relationship_name.strip("'")
    for index, line in enumerate(lines):
        if not line.startswith("relationship "):
            continue
        current_name = _strip_quotes(line[len("relationship "):].strip())
        if current_name != target:
            continue
        start = index
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            if lines[cursor].startswith("relationship "):
                end = cursor
                break
        break
    return start, end


def model_create_relationship(
    project_path: str,
    relationship_name: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    dry_run: bool = False,
) -> dict[str, object]:
    relationships_path = _get_relationships_path(project_path)
    if relationships_path is None:
        return {"error": "SemanticModel directory not found"}
    if not relationships_path.exists():
        return {"error": "relationships.tmdl not found"}

    lines = relationships_path.read_text(encoding="utf-8").splitlines()
    start, end = _find_relationship_block(lines, relationship_name)
    replacement = _relationship_lines(
        relationship_name,
        from_table,
        from_column,
        to_table,
        to_column,
    )

    action = "created"
    new_lines = list(lines)
    if start is not None and end is not None:
        action = "updated"
        block = list(new_lines[start:end])
        from_updated = False
        to_updated = False
        for index, line in enumerate(block):
            if line.startswith("\tfromColumn:"):
                block[index] = f"\tfromColumn: {_format_field_ref(from_table, from_column)}"
                from_updated = True
            elif line.startswith("\ttoColumn:"):
                block[index] = f"\ttoColumn: {_format_field_ref(to_table, to_column)}"
                to_updated = True
        if not from_updated:
            block.insert(1, f"\tfromColumn: {_format_field_ref(from_table, from_column)}")
        if not to_updated:
            insert_index = 2 if from_updated or len(block) > 1 else 1
            block.insert(insert_index, f"\ttoColumn: {_format_field_ref(to_table, to_column)}")
        new_lines[start:end] = block
    else:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.extend(replacement)

    new_text = "\n".join(new_lines).rstrip() + "\n"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "action": action,
            "relationships_path": str(relationships_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    backup = backup_file(relationships_path)
    relationships_path.write_text(new_text, encoding="utf-8")

    fail = _validate_post_tmdl(project_path, str(relationships_path), backup)
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "action": action,
        "relationships_path": str(relationships_path),
        "backup_file": backup,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def model_update_table_description(
    project_path: str,
    table_name: str,
    description: str,
    dry_run: bool = False,
) -> dict[str, object]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is None:
        return {"error": "SemanticModel directory not found"}
    if not tables_dir.exists():
        return {"error": "Tables directory not found"}

    table_path = safe_child(tables_dir, f"{table_name}.tmdl")
    if not table_path.exists():
        return {"error": f"Table not found: {table_name}"}

    lines = table_path.read_text(encoding="utf-8").splitlines()
    description_line = f"\tdescription: {description}"
    action = "created"

    description_index = next((i for i, line in enumerate(lines) if line.startswith("\tdescription:")), None)
    new_lines = list(lines)
    if description_index is not None:
        action = "updated"
        new_lines[description_index] = description_line
    else:
        insert_at = _find_top_level_object_insert_index(new_lines)
        new_lines.insert(insert_at, description_line)
        new_lines.insert(insert_at + 1, "")

    new_text = "\n".join(new_lines).rstrip() + "\n"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "action": action,
            "table_path": str(table_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    backup = backup_file(table_path)
    table_path.write_text(new_text, encoding="utf-8")

    fail = _validate_post_tmdl(project_path, str(table_path), backup)
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "action": action,
        "table_path": str(table_path),
        "backup_file": backup,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def model_update_column_metadata(
    project_path: str,
    table_name: str,
    column_name: str,
    description: str | None = None,
    summarize_by: str | None = None,
    format_string: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is None:
        return {"error": "SemanticModel directory not found"}
    if not tables_dir.exists():
        return {"error": "Tables directory not found"}

    table_path = safe_child(tables_dir, f"{table_name}.tmdl")
    if not table_path.exists():
        return {"error": f"Table not found: {table_name}"}

    lines = table_path.read_text(encoding="utf-8").splitlines()
    start, end = _find_table_object_block(lines, "\tcolumn ", column_name)
    if start is None or end is None:
        return {"error": f"Column not found: {column_name}"}

    block = list(lines[start:end])

    def upsert_property(prefix: str, value: str) -> None:
        for index, line in enumerate(block):
            if line.startswith(prefix):
                block[index] = f"{prefix}{value}"
                return
        insert_index = next(
            (
                index
                for index, line in enumerate(block[1:], start=1)
                if line.startswith("\t\tannotation ") or line.startswith("\t\tchangedProperty ")
            ),
            len(block),
        )
        block.insert(insert_index, f"{prefix}{value}")

    if description is not None:
        upsert_property("\t\tdescription: ", description)
    if summarize_by is not None:
        upsert_property("\t\tsummarizeBy: ", summarize_by)
    if format_string is not None:
        upsert_property("\t\tformatString: ", format_string)

    new_lines = list(lines)
    new_lines[start:end] = block
    new_text = "\n".join(new_lines).rstrip() + "\n"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "table_path": str(table_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    backup = backup_file(table_path)
    table_path.write_text(new_text, encoding="utf-8")

    fail = _validate_post_tmdl(project_path, str(table_path), backup)
    if fail is not None:
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    return {
        "success": True,
        "dry_run": False,
        "table_path": str(table_path),
        "backup_file": backup,
        "validation": ValidationReport.ok_report().to_dict(),
    }


def model_upsert_role(
    project_path: str,
    role_name: str,
    table_name: str,
    dax_filter_expression: str,
    dry_run: bool = False,
) -> dict[str, object]:
    roles_dir = _get_roles_dir(project_path)
    if roles_dir is None:
        return {"error": "SemanticModel directory not found"}
    roles_dir.mkdir(exist_ok=True)

    role_path = safe_child(roles_dir, f"{role_name}.tmdl")
    permission_line = f"\ttablePermission {table_name} = {dax_filter_expression}"
    action = "created"

    if role_path.exists():
        lines = role_path.read_text(encoding="utf-8").splitlines()
        action = "updated"
        updated = False
        for index, line in enumerate(lines):
            if line.startswith(f"\ttablePermission {table_name} = "):
                lines[index] = permission_line
                updated = True
                break
        if not updated:
            insert_at = next(
                (index for index, line in enumerate(lines) if line.startswith("\tannotation ")),
                len(lines),
            )
            lines.insert(insert_at, permission_line)
            lines.insert(insert_at + 1, "")
        new_text = "\n".join(lines).rstrip() + "\n"
    else:
        new_text = "\n".join(
            [
                f"role {_format_role_name(role_name)}",
                "\tmodelPermission: read",
                "",
                permission_line,
                "",
            ]
        ) + "\n"

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "action": action,
            "role_path": str(role_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }

    backup = backup_file(role_path) if role_path.exists() else None
    role_path.write_text(new_text, encoding="utf-8")

    fail = _validate_post_tmdl(project_path, str(role_path), backup)
    if fail is not None:
        if backup is None:  # new file, not restored — delete it
            role_path.unlink(missing_ok=True)
        return {"success": False, "error": "post-validation failed", "validation": fail.to_dict()}

    result: dict[str, object] = {
        "success": True,
        "dry_run": False,
        "action": action,
        "role_path": str(role_path),
        "validation": ValidationReport.ok_report().to_dict(),
    }
    if backup is not None:
        result["backup_file"] = backup
    return result


def model_create_table(
    project_path: str,
    table_name: str,
    columns: list[dict[str, str]],
    source_expression: str,
    query_group: str = "DataModel",
    dry_run: bool = False,
) -> dict[str, object]:
    tables_dir = _get_tables_dir(project_path)
    if tables_dir is None:
        return {"error": "SemanticModel directory not found"}

    table_path = safe_child(tables_dir, f"{table_name}.tmdl")

    # Format the M expression with correct indentation (4 tabs)
    indented_source_lines = []
    for line in source_expression.splitlines():
        if line.strip():
            indented_source_lines.append(f"\t\t\t\t{line}")
        else:
            indented_source_lines.append("")
    indented_source = "\n".join(indented_source_lines)

    table_uuid = str(uuid.uuid4())
    escaped_table_name = _format_identifier(table_name)

    tmdl_lines = [
        f"table {escaped_table_name}",
        f"\tlineageTag: {table_uuid}",
        ""
    ]

    for col in columns:
        col_name = col.get("name")
        col_type = col.get("dataType", "string")
        col_summarize = col.get("summarizeBy", "none")
        col_source = col.get("sourceColumn", col_name)
        col_uuid = str(uuid.uuid4())

        escaped_col_name = _format_identifier(col_name)
        escaped_col_source = _format_identifier(col_source)

        tmdl_lines.extend([
            f"\tcolumn {escaped_col_name}",
            f"\t\tdataType: {col_type}",
            f"\t\tlineageTag: {col_uuid}",
            f"\t\tsummarizeBy: {col_summarize}",
            f"\t\tsourceColumn: {escaped_col_source}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            ""
        ])

    partition_name = f"{table_name}-partition"
    escaped_partition_name = _format_identifier(partition_name)

    tmdl_lines.extend([
        f"\tpartition {escaped_partition_name} = m",
        "\t\tmode: import",
    ])
    if query_group:
        tmdl_lines.append(f"\t\tqueryGroup: {query_group}")

    tmdl_lines.extend([
        "\t\tsource =",
        indented_source,
        "",
        "\tannotation PBI_ResultType = Table"
    ])

    tmdl_content = "\n".join(tmdl_lines).rstrip() + "\n"

    # Manage model.tmdl registration
    model_dir = get_project_summary_paths(project_path).model_dir
    model_path = model_dir / "definition" / "model.tmdl" if model_dir else None

    registered = False
    model_text = ""
    new_model_lines = []

    if model_path and model_path.exists():
        model_lines = model_path.read_text(encoding="utf-8").splitlines()

        # Check if table already registered
        ref_line = f"ref table {escaped_table_name}"

        for line in model_lines:
            if line.startswith("ref table ") and (_strip_quotes(line[len("ref table "):].strip()) == table_name.strip("'")):
                registered = True
                break

        if not registered:
            # Find the last "ref table " line to insert after it
            insert_idx = -1
            for idx, line in enumerate(model_lines):
                if line.startswith("ref table "):
                    insert_idx = idx

            new_model_lines = list(model_lines)
            if insert_idx != -1:
                new_model_lines.insert(insert_idx + 1, ref_line)
            else:
                new_model_lines.append(ref_line)

            # Update PBI_QueryOrder annotation if present
            for idx, line in enumerate(new_model_lines):
                if line.startswith("\tannotation PBI_QueryOrder ="):
                    try:
                        match = re.search(r"=\s*(.+)$", line)
                        if match:
                            list_str = match.group(1)
                            query_list = json.loads(list_str)
                            if isinstance(query_list, list) and table_name not in query_list:
                                query_list.append(table_name)
                                new_model_lines[idx] = f"\tannotation PBI_QueryOrder = {json.dumps(query_list, ensure_ascii=False)}"
                    except Exception:
                        pass

            model_text = "\n".join(new_model_lines).rstrip() + "\n"

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "action": "updated" if table_path.exists() else "created",
            "table_path": str(table_path),
            "model_path": str(model_path) if not registered and model_path and model_path.exists() else None,
            "validation": ValidationReport.ok_report().to_dict(),
        }

    table_backup = None
    model_backup = None

    try:
        tables_dir.mkdir(exist_ok=True)

        if table_path.exists():
            table_backup = backup_file(table_path)
        if model_path and model_path.exists() and not registered:
            model_backup = backup_file(model_path)

        table_path.write_text(tmdl_content, encoding="utf-8")

        if model_path and model_path.exists() and not registered:
            model_path.write_text(model_text, encoding="utf-8")

        touched = [str(table_path)]
        if model_path and model_path.exists() and not registered:
            touched.append(str(model_path))

        report = post_validate_paths(project_path, touched)
        if report.has_errors():
            if table_backup is not None:
                restore_from_backup(table_path, table_backup)
            else:
                table_path.unlink(missing_ok=True)

            if model_backup is not None:
                restore_from_backup(model_path, model_backup)

            return {
                "success": False,
                "error": "post-validation failed",
                "validation": report.to_dict()
            }

        result = {
            "success": True,
            "dry_run": False,
            "action": "updated" if table_backup is not None else "created",
            "table_path": str(table_path),
            "validation": ValidationReport.ok_report().to_dict(),
        }
        if table_backup is not None:
            result["backup_file"] = table_backup
        if model_backup is not None:
            result["model_backup_file"] = model_backup
        return result

    except Exception as e:
        if table_backup is not None:
            restore_from_backup(table_path, table_backup)
        elif table_path.exists():
            table_path.unlink(missing_ok=True)

        if model_backup is not None:
            restore_from_backup(model_path, model_backup)

        return {
            "success": False,
            "error": f"Exception occurred: {str(e)}",
            "validation": ValidationReport.ok_report().to_dict(),
        }


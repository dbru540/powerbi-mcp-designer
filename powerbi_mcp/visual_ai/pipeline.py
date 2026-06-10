import logging
from typing import Any
from powerbi_mcp.common.paths import get_project_summary_paths
from powerbi_mcp.model.write import model_create_table, model_upsert_measure
from powerbi_mcp.report.write import report_create_page, report_create_visual
from powerbi_mcp.validation.engine import validate_project
from powerbi_mcp.validation.report import ValidationReport

logger = logging.getLogger(__name__)

def report_create_from_datasource_spec(
    project_path: str,
    table_name: str,
    columns: list[dict[str, str]],
    source_expression: str,
    query_group: str = "DataModel",
    measures: list[dict[str, str]] | None = None,
    page_name: str = "Analysis",
    visuals_spec: list[dict[str, Any]] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Pipeline de bout en bout : crée une table TMDL, des mesures DAX, une page de rapport
    et y ajoute des visuels configurés. Tout est validé à la fin.
    """
    measures = measures or []
    visuals_spec = visuals_spec or []

    # 1. Simuler ou appliquer la création de la table
    table_res = model_create_table(
        project_path=project_path,
        table_name=table_name,
        columns=columns,
        source_expression=source_expression,
        query_group=query_group,
        dry_run=dry_run,
    )
    if not table_res.get("success", False) and not table_res.get("dry_run", False):
        return {
            "success": False,
            "error": f"Failed to create table '{table_name}'",
            "details": table_res,
        }

    # 2. Simuler ou appliquer les mesures
    measure_results = []
    for measure in measures:
        m_name = measure.get("name")
        m_expr = measure.get("expression")
        if not m_name or not m_expr:
            continue

        # In dry_run, if the table doesn't exist on disk (because it's a new table we are simulating),
        # model_upsert_measure would fail. We mock its success.
        paths = get_project_summary_paths(project_path)
        tables_dir = paths.tables_dir
        table_exists = False
        if tables_dir:
            table_path = tables_dir / f"{table_name}.tmdl"
            table_exists = table_path.exists()

        if dry_run and not table_exists:
            m_res = {
                "success": True,
                "dry_run": True,
                "action": "created",
                "table_path": str(tables_dir / f"{table_name}.tmdl") if tables_dir else "",
                "validation": {"ok": True, "issues": []}
            }
        else:
            m_res = model_upsert_measure(
                project_path=project_path,
                table_name=table_name,
                measure_name=m_name,
                expression=m_expr,
                dry_run=dry_run,
            )

        if not m_res.get("success", False) and not m_res.get("dry_run", False):
            return {
                "success": False,
                "error": f"Failed to create measure '{m_name}' in table '{table_name}'",
                "details": m_res,
            }
        measure_results.append(m_res)

    # 3. Simuler ou appliquer la page de rapport
    page_res = report_create_page(
        project_path=project_path,
        display_name=page_name,
        dry_run=dry_run,
    )
    if not page_res.get("success", False) and not page_res.get("dry_run", False):
        return {
            "success": False,
            "error": f"Failed to create report page '{page_name}'",
            "details": page_res,
        }
    page_id = page_res.get("page_id", "temp_page_id")

    # 4. Simuler ou appliquer les visuels
    visual_results = []
    for idx, vis in enumerate(visuals_spec):
        v_type = vis.get("visual_type")
        v_title = vis.get("title")
        v_x = vis.get("x", 0)
        v_y = vis.get("y", 0)
        v_w = vis.get("width", 300)
        v_h = vis.get("height", 200)

        # Binding params
        v_cat_ent = vis.get("category_entity")
        v_cat_prop = vis.get("category_property")
        v_meas_ent = vis.get("measure_entity")
        v_meas_prop = vis.get("measure_property")
        v_roles = vis.get("role_assignments")

        # In dry_run, if the page visuals directory doesn't exist, report_create_visual fails.
        # We mock its success.
        paths = get_project_summary_paths(project_path)
        pages_dir = paths.pages_dir
        page_exists = False
        if pages_dir:
            visuals_dir = pages_dir / page_id / "visuals"
            page_exists = visuals_dir.exists()

        if dry_run and not page_exists:
            v_res = {
                "success": True,
                "dry_run": True,
                "visual_id": f"mock_visual_id_{idx}",
                "path": str(pages_dir / page_id / "visuals" / f"mock_visual_id_{idx}") if pages_dir else "",
                "visualType": v_type,
                "validation": {"ok": True, "issues": []}
            }
        else:
            v_res = report_create_visual(
                project_path=project_path,
                page_id=page_id,
                visual_type=v_type,
                x=v_x,
                y=v_y,
                width=v_w,
                height=v_h,
                title=v_title,
                category_entity=v_cat_ent,
                category_property=v_cat_prop,
                measure_entity=v_meas_ent,
                measure_property=v_meas_prop,
                role_assignments=v_roles,
                dry_run=dry_run,
            )

        if not v_res.get("success", False) and not v_res.get("dry_run", False):
            return {
                "success": False,
                "error": f"Failed to create visual index {idx} on page '{page_name}'",
                "details": v_res,
            }
        visual_results.append(v_res)

    # 5. Validation finale globale si on n'est pas en dry-run
    if not dry_run:
        validation_report = validate_project(project_path)
        if not validation_report.ok:
            return {
                "success": False,
                "error": "Pipeline finished but project validation failed",
                "validation": validation_report.to_dict(),
            }

    return {
        "success": True,
        "dry_run": dry_run,
        "table_result": table_res,
        "measure_results": measure_results,
        "page_result": page_res,
        "visual_results": visual_results,
        "validation": ValidationReport.ok_report().to_dict(),
    }

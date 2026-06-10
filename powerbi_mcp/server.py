"""
Power BI MCP Server - Serveur MCP pour manipuler les rapports Power BI (PBIR/PBIP)

Ce serveur expose des tools generiques que Claude Code peut appeler
avec differents parametres pour lire/modifier les rapports Power BI.
"""

import argparse
import os
import json
import shutil
import sys
import uuid
from typing import List, Optional, Dict, Any
from pathlib import Path



from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from powerbi_mcp.common.paths import (
    find_report_dir,
    get_project_summary_paths,
)
from powerbi_mcp.visual_ai.vocabulary import visual_vocabulary_classify as read_visual_vocabulary_classify
from powerbi_mcp.visual_ai.critic import report_design_audit as read_report_design_audit
from powerbi_mcp.visual_ai.critic import page_design_audit as read_page_design_audit
from powerbi_mcp.visual_ai.critic import visual_design_audit as read_visual_design_audit
from powerbi_mcp.visual_ai.improvements import report_design_improve_plan as read_report_design_improve_plan
from powerbi_mcp.visual_ai.improvements import page_design_improve_plan as read_page_design_improve_plan
from powerbi_mcp.visual_ai.studio import report_design_studio_plan as read_report_design_studio_plan
from powerbi_mcp.visual_ai.readiness import report_design_readiness_check as read_report_design_readiness_check
from powerbi_mcp.visual_ai.qa_loop import run_file_first_visual_qa_loop as read_run_file_first_visual_qa_loop
from powerbi_mcp.visual_ai.desktop_evidence import report_design_desktop_evidence_summary as read_report_design_desktop_evidence_summary
from powerbi_mcp.visual_ai.workbench import page_design_action_plan as read_page_design_action_plan
from powerbi_mcp.visual_ai.workbench import page_design_apply_quick_wins as write_page_design_apply_quick_wins
from powerbi_mcp.visual_ai.workbench import report_design_apply_quick_wins as write_report_design_apply_quick_wins
from powerbi_mcp.visual_ai.workbench import page_layout_action_plan as read_page_layout_action_plan
from powerbi_mcp.visual_ai.workbench import page_layout_apply_quick_wins as write_page_layout_apply_quick_wins
from powerbi_mcp.visual_ai.workbench import report_layout_apply_quick_wins as write_report_layout_apply_quick_wins
from powerbi_mcp.visual_ai.layout import page_layout_analyze as read_page_layout_analyze
from powerbi_mcp.visual_ai.layout import page_layout_blueprint_generate as write_page_layout_blueprint_generate
from powerbi_mcp.visual_ai.layout import page_layout_recommend as read_page_layout_recommend
from powerbi_mcp.visual_ai.layout import page_layout_reflow_plan as read_page_layout_reflow_plan
from powerbi_mcp.visual_ai.workbench import page_layout_apply_reflow_plan as write_page_layout_apply_reflow_plan
from powerbi_mcp.visual_ai.catalog import visual_catalog_list as read_visual_catalog_list
from powerbi_mcp.visual_ai.catalog import visual_requirements_check as read_visual_requirements_check
from powerbi_mcp.visual_ai.examples import custom_visual_eligibility as read_custom_visual_eligibility
from powerbi_mcp.visual_ai.examples import visual_examples_list as read_visual_examples_list
from powerbi_mcp.visual_ai.examples import visual_role_examples as read_visual_role_examples
from powerbi_mcp.visual_ai.examples import visual_template_library as read_visual_template_library
from powerbi_mcp.visual_ai.examples import visual_template_recommend as read_visual_template_recommend
from powerbi_mcp.visual_ai.planner import visual_plan_generate as read_visual_plan_generate
from powerbi_mcp.visual_ai.compiler import visual_plan_apply as write_visual_plan_apply
from powerbi_mcp.visual_ai.compiler import visual_plan_generate_and_apply as write_visual_plan_generate_and_apply
from powerbi_mcp.visual_ai.design_expert import report_design_brief_generate as read_report_design_brief_generate

from powerbi_mcp.report.read import project_get_summary as read_project_get_summary
from powerbi_mcp.report.read import report_get_summary as read_report_get_summary
from powerbi_mcp.report.read import report_list_pages as read_report_list_pages
from powerbi_mcp.report.read import report_get_page as read_report_get_page
from powerbi_mcp.report.read import report_list_visuals as read_report_list_visuals
from powerbi_mcp.report.read import report_get_visual as read_report_get_visual
from powerbi_mcp.analysis.bindings import report_get_visual_bindings as read_report_get_visual_bindings
from powerbi_mcp.analysis.bindings import find_report_objects_by_model_reference as read_find_report_objects_by_model_reference
from powerbi_mcp.analysis.impact import find_unused_measures as read_find_unused_measures
from powerbi_mcp.analysis.impact import impact_of_model_reference as read_impact_of_model_reference
from powerbi_mcp.interop.powerbi_modeling_mcp import get_powerbi_modeling_mcp_interop_guidance as read_get_powerbi_modeling_mcp_interop_guidance

from powerbi_mcp.report.write import report_create_page as write_report_create_page
from powerbi_mcp.report.write import report_create_visual as write_report_create_visual
from powerbi_mcp.report.write import report_move_visual as write_report_move_visual
from powerbi_mcp.report.write import report_update_visual_title as write_report_update_visual_title
from powerbi_mcp.report.write import report_update_page_size as write_report_update_page_size
from powerbi_mcp.report.write import report_rename_page as write_report_rename_page
from powerbi_mcp.report.write import report_update_visual_json as write_report_update_visual_json
from powerbi_mcp.report.write import report_extract_visual_config as write_report_extract_visual_config
from powerbi_mcp.report.write import report_apply_visual_style as write_report_apply_visual_style
from powerbi_mcp.report.write import report_clone_visual_style as write_report_clone_visual_style
from powerbi_mcp.report.write import report_create_deneb_visual as write_report_create_deneb_visual
from powerbi_mcp.model.read import model_get_summary as read_model_get_summary
from powerbi_mcp.model.read import model_list_tables as read_model_list_tables
from powerbi_mcp.model.read import model_list_relationships as read_model_list_relationships
from powerbi_mcp.model.read import model_list_measures as read_model_list_measures
from powerbi_mcp.model.write import model_upsert_measure as write_model_upsert_measure
from powerbi_mcp.model.write import model_create_relationship as write_model_create_relationship
from powerbi_mcp.model.write import model_update_table_description as write_model_update_table_description
from powerbi_mcp.model.write import model_update_column_metadata as write_model_update_column_metadata
from powerbi_mcp.model.write import model_upsert_role as write_model_upsert_role
from powerbi_mcp.model.write import model_create_table as write_model_create_table
from powerbi_mcp.visual_ai.pipeline import report_create_from_datasource_spec as write_report_create_from_datasource_spec
from powerbi_mcp.model.read import get_table_content as model_get_table_content
from powerbi_mcp.validation.engine import validate_project
from powerbi_mcp.validation.engine import validate_report
from powerbi_mcp.validation.engine import validate_model

# =============================================================================
# INITIALISATION DU SERVEUR MCP
# =============================================================================

MUTATING_TOOL_PREFIXES = (
    "apply_",
    "batch_update_",
    "clone_",
    "copy_",
    "create_",
    "delete_",
    "duplicate_",
    "model_create_",
    "model_update_",
    "model_upsert_",
    "rename_",
    "report_create_",
    "set_",
    "update_",
)

MUTATING_TOOL_NAMES = {
    "page_design_apply_quick_wins",
    "page_layout_apply_quick_wins",
    "page_layout_apply_reflow_plan",
    "report_design_apply_quick_wins",
    "report_layout_apply_quick_wins",
    "visual_plan_apply",
    "visual_plan_generate_and_apply",
}

OPEN_WORLD_TOOL_NAMES = {
    "report_design_visual_qa_loop",
}


def _annotations_for_tool(tool_name: str) -> ToolAnnotations:
    if tool_name in OPEN_WORLD_TOOL_NAMES:
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        )
    if tool_name in MUTATING_TOOL_NAMES or tool_name.startswith(MUTATING_TOOL_PREFIXES):
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        )
    return ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


class AnnotatedFastMCP(FastMCP):
    """FastMCP wrapper that prevents MCP clients from falling back to misleading default hints."""

    def tool(
        self,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Any] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ):
        def decorator(fn):
            tool_name = name or fn.__name__
            return super(AnnotatedFastMCP, self).tool(
                name=name,
                title=title,
                description=description,
                annotations=annotations or _annotations_for_tool(tool_name),
                icons=icons,
                meta=meta,
                structured_output=structured_output,
            )(fn)

        return decorator


mcp = AnnotatedFastMCP(
    "PowerBI-MCP-Server",
    instructions=(
        "Use this local MCP server to inspect and safely edit Power BI PBIP/PBIR/TMDL projects. "
        "Prefer read-only analysis tools before write tools, validate projects after mutations, "
        "and only operate on project paths explicitly provided by the user."
    ),
)


# =============================================================================
# UTILITAIRES
# =============================================================================

class PBIIDGenerator:
    """Generateur d'IDs uniques pour Power BI (20 caracteres hex)"""

    @staticmethod
    def generate() -> str:
        return uuid.uuid4().hex[:20]


def get_pages_dir(project_path: str) -> Optional[Path]:
    """Retourne le chemin vers le dossier pages"""
    return get_project_summary_paths(project_path).pages_dir


# =============================================================================
# TOOLS DE LECTURE
# =============================================================================

@mcp.tool()
def list_reports(directory: str) -> Dict[str, Any]:
    """
    Liste tous les projets Power BI (.pbip) dans un repertoire.

    Args:
        directory: Chemin vers le repertoire a scanner

    Returns:
        Liste des projets trouves avec leurs chemins
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return {"error": f"Directory not found: {directory}"}

    reports = []
    for item in dir_path.iterdir():
        if item.is_file() and item.suffix == ".pbip":
            reports.append({
                "name": item.stem,
                "path": str(item.parent),
                "pbip_file": str(item)
            })
        elif item.is_dir():
            # Chercher les .pbip dans les sous-dossiers
            for subitem in item.glob("*.pbip"):
                reports.append({
                    "name": subitem.stem,
                    "path": str(subitem.parent),
                    "pbip_file": str(subitem)
                })

    return {"reports": reports, "count": len(reports)}


@mcp.tool()
def visual_vocabulary_classify(
    intent: str,
    audience: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classe l'intention analytique/presentation avant le choix du type de visuel.
    """
    return read_visual_vocabulary_classify(intent=intent, audience=audience)


@mcp.tool()
def report_design_audit(
    project_path: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
    visual_qa_report_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audite la qualite design d'un rapport Power BI PBIR sans modifier les fichiers.
    """
    return read_report_design_audit(
        project_path=project_path,
        audience=audience,
        intent=intent,
        visual_qa_report_file=visual_qa_report_file,
    )


@mcp.tool()
def page_design_audit(
    project_path: str,
    page_id: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audite la qualite design d'une page Power BI PBIR sans modifier les fichiers.
    """
    return read_page_design_audit(project_path=project_path, page_id=page_id, audience=audience, intent=intent)


@mcp.tool()
def visual_design_audit(
    project_path: str,
    page_id: str,
    visual_id: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audite la qualite design d'un visuel Power BI PBIR sans modifier les fichiers.
    """
    return read_visual_design_audit(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        audience=audience,
        intent=intent,
    )


@mcp.tool()
def report_design_improve_plan(
    project_path: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produit un plan priorise d'amelioration design du rapport sans modifier les fichiers.
    """
    return read_report_design_improve_plan(project_path=project_path, audience=audience, intent=intent)


@mcp.tool()
def page_design_improve_plan(
    project_path: str,
    page_id: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produit un plan priorise d'amelioration design d'une page sans modifier les fichiers.
    """
    return read_page_design_improve_plan(project_path=project_path, page_id=page_id, audience=audience, intent=intent)


@mcp.tool()
def report_design_studio_plan(
    project_path: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    page_limit: int = 3,
    visual_qa_report_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Orchestre critic, layout, quick wins et reflow dans un plan de studio read-only.
    """
    return read_report_design_studio_plan(
        project_path=project_path,
        audience=audience,
        intent=intent,
        subject=subject,
        page_limit=page_limit,
        visual_qa_report_file=visual_qa_report_file,
    )


@mcp.tool()
def report_design_readiness_check(
    project_path: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    page_limit: int = 1,
) -> Dict[str, Any]:
    """
    Evalue si le serveur est pret pour le design Power BI assiste par IA et liste les gates restants.
    """
    return read_report_design_readiness_check(
        project_path=project_path,
        audience=audience,
        intent=intent,
        subject=subject,
        page_limit=page_limit,
    )


@mcp.tool()
def report_design_visual_qa_loop(
    test_root: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    pbidesktop_path: Optional[str] = None,
    launch_desktop: bool = False,
    capture_screenshot: bool = False,
    capture_all_pages: bool = False,
    desktop_wait_seconds: float = 45,
    screenshot_page_limit: Optional[int] = None,
    page_navigation_delay_seconds: float = 2,
    render_readiness_retry_seconds: float = 0,
    render_readiness_retry_interval_seconds: float = 5,
    baseline_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    page_limit: int = 1,
) -> Dict[str, Any]:
    """
    Execute une boucle QA file-first pour valider les rapports PBIP et preparer le rendu Desktop optionnel.
    """
    return read_run_file_first_visual_qa_loop(
        test_root=test_root,
        audience=audience,
        intent=intent,
        subject=subject,
        pbidesktop_path=pbidesktop_path,
        launch_desktop=launch_desktop,
        capture_screenshot=capture_screenshot,
        capture_all_pages=capture_all_pages,
        desktop_wait_seconds=desktop_wait_seconds,
        screenshot_page_limit=screenshot_page_limit,
        page_navigation_delay_seconds=page_navigation_delay_seconds,
        render_readiness_retry_seconds=render_readiness_retry_seconds,
        render_readiness_retry_interval_seconds=render_readiness_retry_interval_seconds,
        baseline_dir=baseline_dir,
        output_dir=output_dir,
        page_limit=page_limit,
    )


@mcp.tool()
def report_design_desktop_evidence_summary(report_file: str) -> Dict[str, Any]:
    """
    Resume les captures Desktop d'un visual-qa-report.json pour savoir quelles pages sont exploitables.
    """
    return read_report_design_desktop_evidence_summary(report_file)


@mcp.tool()
def page_design_action_plan(
    project_path: str,
    page_id: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
    max_actions: int = 5,
) -> Dict[str, Any]:
    """
    Produit une liste d'actions design executables sans modifier les fichiers.
    """
    return read_page_design_action_plan(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        max_actions=max_actions,
    )


@mcp.tool()
def page_design_apply_quick_wins(
    project_path: str,
    page_id: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
    max_actions: int = 5,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique les quick wins design a faible risque sur une page, en dry-run par defaut.
    """
    return write_page_design_apply_quick_wins(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        max_actions=max_actions,
        dry_run=dry_run,
    )


@mcp.tool()
def report_design_apply_quick_wins(
    project_path: str,
    audience: Optional[str] = None,
    intent: Optional[str] = None,
    page_limit: Optional[int] = None,
    max_actions_per_page: int = 5,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique les quick wins design a faible risque sur un rapport, en dry-run par defaut.
    """
    return write_report_design_apply_quick_wins(
        project_path=project_path,
        audience=audience,
        intent=intent,
        page_limit=page_limit,
        max_actions_per_page=max_actions_per_page,
        dry_run=dry_run,
    )


@mcp.tool()
def page_layout_action_plan(
    project_path: str,
    page_id: str,
    grid_size: int = 8,
    max_actions: int = 5,
) -> Dict[str, Any]:
    """
    Produit des actions de layout executables pour aligner les visuels sur une grille.
    """
    return read_page_layout_action_plan(
        project_path=project_path,
        page_id=page_id,
        grid_size=grid_size,
        max_actions=max_actions,
    )


@mcp.tool()
def page_layout_apply_quick_wins(
    project_path: str,
    page_id: str,
    grid_size: int = 8,
    max_actions: int = 5,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique des quick wins de layout sur une page, en dry-run par defaut.
    """
    return write_page_layout_apply_quick_wins(
        project_path=project_path,
        page_id=page_id,
        grid_size=grid_size,
        max_actions=max_actions,
        dry_run=dry_run,
    )


@mcp.tool()
def report_layout_apply_quick_wins(
    project_path: str,
    page_limit: Optional[int] = None,
    grid_size: int = 8,
    max_actions_per_page: int = 5,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique des quick wins de layout sur un rapport, en dry-run par defaut.
    """
    return write_report_layout_apply_quick_wins(
        project_path=project_path,
        page_limit=page_limit,
        grid_size=grid_size,
        max_actions_per_page=max_actions_per_page,
        dry_run=dry_run,
    )


@mcp.tool()
def page_layout_analyze(
    project_path: str,
    page_id: str,
    overlap_threshold: float = 25.0,
) -> Dict[str, Any]:
    """
    Analyse la structure visuelle d'une page: zones, focal points et overlaps.
    """
    return read_page_layout_analyze(
        project_path=project_path,
        page_id=page_id,
        overlap_threshold=overlap_threshold,
    )


@mcp.tool()
def page_layout_blueprint_generate(
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    page_width: int = 1280,
    page_height: int = 720,
) -> Dict[str, Any]:
    """
    Genere un blueprint de layout Power BI adapte a l'audience et au besoin.
    """
    return read_page_layout_blueprint_generate(
        audience=audience,
        intent=intent,
        subject=subject,
        page_width=page_width,
        page_height=page_height,
    )


@mcp.tool()
def page_layout_recommend(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compare une page existante a un blueprint et recommande les corrections design.
    """
    return read_page_layout_recommend(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        subject=subject,
    )


@mcp.tool()
def page_layout_reflow_plan(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    max_moves: int = 5,
) -> Dict[str, Any]:
    """
    Produit un plan de reflow executable en mappant les visuels existants au blueprint.
    """
    return read_page_layout_reflow_plan(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        subject=subject,
        max_moves=max_moves,
    )


@mcp.tool()
def page_layout_apply_reflow_plan(
    project_path: str,
    page_id: str,
    audience: str,
    intent: str,
    subject: Optional[str] = None,
    max_moves: int = 5,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique un plan de reflow de page, en dry-run par defaut.
    """
    return write_page_layout_apply_reflow_plan(
        project_path=project_path,
        page_id=page_id,
        audience=audience,
        intent=intent,
        subject=subject,
        max_moves=max_moves,
        dry_run=dry_run,
    )


@mcp.tool()
def visual_catalog_list() -> Dict[str, Any]:
    """
    Liste le catalogue initial des familles de visuels supportees par la couche IA.
    """
    return read_visual_catalog_list()


@mcp.tool()
def visual_requirements_check(
    visual_type: str,
    assignments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Verifie si les roles fournis couvrent les exigences minimales d'un visuel.
    """
    return read_visual_requirements_check(visual_type, assignments)


@mcp.tool()
def visual_examples_list(
    project_path: str,
    visual_type: Optional[str] = None,
    supported_only: bool = False,
    max_examples_per_type: Optional[int] = 3,
) -> Dict[str, Any]:
    """
    Extrait des exemples compacts de visuels reels depuis un projet PBIR local.
    """
    return read_visual_examples_list(
        project_path=project_path,
        visual_type=visual_type,
        supported_only=supported_only,
        max_examples_per_type=max_examples_per_type,
    )


@mcp.tool()
def visual_template_recommend(
    project_path: str,
    visual_type: str,
) -> Dict[str, Any]:
    """
    Recommande un exemple PBIR local comme point de reference pour un type de visuel.
    """
    return read_visual_template_recommend(
        project_path=project_path,
        visual_type=visual_type,
    )


@mcp.tool()
def visual_template_library(
    project_path: str,
    supported_only: bool = False,
    max_templates_per_type: int = 1,
) -> Dict[str, Any]:
    """
    Construit une bibliotheque de templates PBIR par type de visuel depuis un projet local.
    """
    return read_visual_template_library(
        project_path=project_path,
        supported_only=supported_only,
        max_templates_per_type=max_templates_per_type,
    )


@mcp.tool()
def visual_role_examples(
    project_path: str,
    visual_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resume les roles Power BI reels observes dans les visual.json: Values, Category, Y, Rows, Columns.
    """
    return read_visual_role_examples(
        project_path=project_path,
        visual_type=visual_type,
    )


@mcp.tool()
def custom_visual_eligibility(project_path: str) -> Dict[str, Any]:
    """
    Detecte les custom visuals du rapport et recommande des fallbacks natifs prudents.
    """
    return read_custom_visual_eligibility(project_path=project_path)


@mcp.tool()
def visual_plan_generate(
    intent: str,
    dimensions: Optional[List[Dict[str, Any]]] = None,
    measures: Optional[List[Dict[str, Any]]] = None,
    audience: Optional[str] = None,
    preferred_path: Optional[str] = None,
    template_project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genere un plan de visuel a partir de l'intention, des dimensions et des mesures.
    """
    return read_visual_plan_generate(
        intent=intent,
        dimensions=dimensions,
        measures=measures,
        audience=audience,
        preferred_path=preferred_path,
        template_project_path=template_project_path,
    )


@mcp.tool()
def visual_plan_apply(
    project_path: str,
    page_id: str,
    plan: Dict[str, Any],
    x: int = 0,
    y: int = 0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    title: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Applique un plan de visuel natif via la couche sure d'ecriture report.write.
    """
    return write_visual_plan_apply(
        project_path=project_path,
        page_id=page_id,
        plan=plan,
        x=x,
        y=y,
        width=width,
        height=height,
        title=title,
        dry_run=dry_run,
    )


@mcp.tool()
def visual_plan_generate_and_apply(
    project_path: str,
    page_id: str,
    intent: str,
    dimensions: Optional[List[Dict[str, Any]]] = None,
    measures: Optional[List[Dict[str, Any]]] = None,
    audience: Optional[str] = None,
    preferred_path: Optional[str] = None,
    template_project_path: Optional[str] = None,
    x: int = 0,
    y: int = 0,
    width: Optional[int] = None,
    height: Optional[int] = None,
    title: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Genere un plan de visuel puis l'applique si le chemin natif PBIR est supporte.
    """
    return write_visual_plan_generate_and_apply(
        project_path=project_path,
        page_id=page_id,
        intent=intent,
        dimensions=dimensions,
        measures=measures,
        audience=audience,
        preferred_path=preferred_path,
        template_project_path=template_project_path,
        x=x,
        y=y,
        width=width,
        height=height,
        title=title,
        dry_run=dry_run,
    )


@mcp.tool()
def report_design_brief_generate(
    audience: str,
    intent: str,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produit un brief de design de page de rapport a partir de l'audience et de l'intent.
    """
    return read_report_design_brief_generate(
        audience=audience,
        intent=intent,
        subject=subject,
    )


@mcp.tool()
def project_get_summary(project_path: str) -> Dict[str, Any]:
    """
    Retourne un resume unifie du projet, du rapport et du modele.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Resume compose des chemins du projet, du rapport et du modele
    """
    return read_project_get_summary(project_path)


@mcp.tool()
def report_get_summary(project_path: str) -> Dict[str, Any]:
    """
    Retourne le resume structure du rapport.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Resume du rapport avec comptes de pages et de visuels
    """
    return read_report_get_summary(project_path)


@mcp.tool()
def report_list_pages(project_path: str) -> Dict[str, Any]:
    """
    Liste toutes les pages d'un rapport Power BI.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Liste des pages avec leur ID, nom et nombre de visuels
    """
    return read_report_list_pages(project_path)


@mcp.tool()
def report_get_page(project_path: str, page_id: str) -> Dict[str, Any]:
    """
    Retourne les details d'une page specifique.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page (ex: "ReportSection123...")

    Returns:
        Configuration complete de la page
    """
    return read_report_get_page(project_path, page_id)


@mcp.tool()
def report_list_visuals(project_path: str, page_id: str) -> Dict[str, Any]:
    """
    Liste tous les visuels d'une page.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page

    Returns:
        Liste des visuels avec leur ID, type et position
    """
    return read_report_list_visuals(project_path, page_id)


@mcp.tool()
def report_get_visual(project_path: str, page_id: str, visual_id: str) -> Dict[str, Any]:
    """
    Retourne la configuration complete d'un visuel.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        visual_id: ID du visuel

    Returns:
        Configuration JSON complete du visuel
    """
    return read_report_get_visual(project_path, page_id, visual_id)


@mcp.tool()
def get_project_info(project_path: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `project_get_summary`."""
    return read_project_get_summary(project_path)


@mcp.tool()
def list_pages(project_path: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `report_list_pages`."""
    return read_report_list_pages(project_path)


@mcp.tool()
def get_page(project_path: str, page_id: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `report_get_page`."""
    return read_report_get_page(project_path, page_id)


@mcp.tool()
def list_visuals(project_path: str, page_id: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `report_list_visuals`."""
    return read_report_list_visuals(project_path, page_id)


@mcp.tool()
def get_visual(project_path: str, page_id: str, visual_id: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `report_get_visual`."""
    return read_report_get_visual(project_path, page_id, visual_id)


@mcp.tool()
def report_get_visual_bindings(
    project_path: str,
    page_id: str,
    visual_id: str,
) -> Dict[str, Any]:
    """
    Retourne les projections `queryState` d'un visuel et leurs references modele.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        visual_id: ID du visuel

    Returns:
        Bindings query-state du visuel avec roles et references modele
    """
    return read_report_get_visual_bindings(project_path, page_id, visual_id)


@mcp.tool()
def find_report_objects_by_model_reference(
    project_path: str,
    entity: str,
    property_name: str,
) -> Dict[str, Any]:
    """
    Recherche les visuels qui projettent une reference modele exacte.

    Args:
        project_path: Chemin vers le dossier du projet
        entity: Entite du modele semantique
        property_name: Propriete ou mesure du modele semantique

    Returns:
        Liste des visuels correspondants et des bindings matches
    """
    return read_find_report_objects_by_model_reference(
        project_path,
        entity,
        property_name,
    )


@mcp.tool()
def find_unused_measures(project_path: str) -> Dict[str, Any]:
    """
    Liste les mesures du modele qui ne sont referencees par aucun visuel du rapport.
    """
    return read_find_unused_measures(project_path)


@mcp.tool()
def impact_of_model_reference(
    project_path: str,
    entity: str,
    property_name: str,
) -> Dict[str, Any]:
    """
    Retourne une vue agregee des pages et visuels affectes par une reference modele.
    """
    return read_impact_of_model_reference(project_path, entity, property_name)


@mcp.tool()
def get_powerbi_modeling_mcp_interop_guidance() -> Dict[str, Any]:
    """
    Retourne le partage de responsabilites recommande entre ce serveur et
    `microsoft/powerbi-modeling-mcp`.
    """
    return read_powerbi_modeling_mcp_interop_guidance()


@mcp.tool()
def get_visual_types_summary(project_path: str) -> Dict[str, Any]:
    """
    Retourne un resume des types de visuels utilises dans le rapport.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Comptage par type de visuel
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    type_counts = {}

    for visual_json in pages_dir.glob("*/visuals/*/visual.json"):
        with open(visual_json, 'r', encoding='utf-8') as f:
            v_data = json.load(f)
        visual_type = v_data.get("visual", {}).get("visualType", "unknown")
        type_counts[visual_type] = type_counts.get(visual_type, 0) + 1

    return {
        "types": type_counts,
        "total": sum(type_counts.values())
    }


@mcp.tool()
def find_visuals_by_type(project_path: str, visual_type: str) -> Dict[str, Any]:
    """
    Trouve tous les visuels d'un type specifique.

    Args:
        project_path: Chemin vers le dossier du projet
        visual_type: Type de visuel (ex: "barChart", "lineChart", "card", "slicer")

    Returns:
        Liste des visuels correspondants avec leur page et position
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    results = []

    for visual_json in pages_dir.glob("*/visuals/*/visual.json"):
        with open(visual_json, 'r', encoding='utf-8') as f:
            v_data = json.load(f)

        v_type = v_data.get("visual", {}).get("visualType", "")
        if v_type == visual_type:
            page_id = visual_json.parent.parent.parent.name
            visual_id = visual_json.parent.name

            results.append({
                "page_id": page_id,
                "visual_id": visual_id,
                "position": v_data.get("position", {}),
                "path": str(visual_json)
            })

    return {"visuals": results, "count": len(results)}


# =============================================================================
# TOOLS DE CREATION
# =============================================================================

@mcp.tool()
def create_page(
    project_path: str,
    display_name: str,
    width: int = 1280,
    height: int = 720,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree une nouvelle page dans le rapport.

    Args:
        project_path: Chemin vers le dossier du projet
        display_name: Nom affiche de la page
        width: Largeur en pixels (defaut: 1280)
        height: Hauteur en pixels (defaut: 720)

    Returns:
        ID de la nouvelle page et son chemin
    """
    return write_report_create_page(
        project_path=project_path,
        display_name=display_name,
        width=width,
        height=height,
        dry_run=dry_run,
    )


@mcp.tool()
def create_visual(
    project_path: str,
    page_id: str,
    visual_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    title: Optional[str] = None,
    category_entity: Optional[str] = None,
    category_property: Optional[str] = None,
    measure_entity: Optional[str] = None,
    measure_property: Optional[str] = None,
    role_assignments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree un nouveau visuel sur une page.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page cible
        visual_type: Type de visuel (barChart, lineChart, card, table, slicer, etc.)
        x: Position X en pixels
        y: Position Y en pixels
        width: Largeur en pixels
        height: Hauteur en pixels
        title: Titre du visuel (optionnel)
        category_entity: Entite pour la categorie/axe X (ex: "Projects")
        category_property: Propriete pour la categorie (ex: "Project Name")
        measure_entity: Entite pour la mesure/axe Y (ex: "Budgeted tickets")
        measure_property: Propriete pour la mesure (ex: "Fixed price - Margin")

    Returns:
        ID du nouveau visuel et son chemin
    """
    return write_report_create_visual(
        project_path=project_path,
        page_id=page_id,
        visual_type=visual_type,
        x=x,
        y=y,
        width=width,
        height=height,
        title=title,
        category_entity=category_entity,
        category_property=category_property,
        measure_entity=measure_entity,
        measure_property=measure_property,
        role_assignments=role_assignments,
        dry_run=dry_run,
    )


@mcp.tool()
def create_deneb_visual(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    vega_lite_spec: Any,
    dataset_bindings: List[Dict[str, Any]],
    title: Optional[str] = None,
    vega_lite_config: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree un nouveau visuel Deneb (Vega-Lite) sur une page de rapport.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page cible
        x: Position X en pixels
        y: Position Y en pixels
        width: Largeur en pixels
        height: Hauteur en pixels
        vega_lite_spec: Specification Vega-Lite (dict ou chaine JSON)
        dataset_bindings: Liste de bindings de donnees a projeter.
                          Exemple: [{"entity": "QA_Projects", "property": "ClientName", "kind": "Column"}]
        title: Titre du visuel (optionnel)
        vega_lite_config: Configuration Vega-Lite (optionnel)

    Returns:
        ID du visuel cree et son chemin
    """
    import json
    spec = vega_lite_spec
    if isinstance(vega_lite_spec, str):
        try:
            spec = json.loads(vega_lite_spec)
        except Exception:
            pass
            
    config = vega_lite_config
    if isinstance(vega_lite_config, str) and vega_lite_config:
        try:
            config = json.loads(vega_lite_config)
        except Exception:
            pass

    return write_report_create_deneb_visual(
        project_path=project_path,
        page_id=page_id,
        x=x,
        y=y,
        width=width,
        height=height,
        vega_lite_spec=spec,
        dataset_bindings=dataset_bindings,
        title=title,
        vega_lite_config=config,
        dry_run=dry_run,
    )


@mcp.tool()
def create_card(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    measure_entity: str,
    measure_property: str,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cree une carte KPI affichant une mesure.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page cible
        x, y: Position en pixels
        width, height: Dimensions en pixels
        measure_entity: Entite contenant la mesure
        measure_property: Nom de la mesure
        title: Titre de la carte (optionnel)

    Returns:
        ID du nouveau visuel
    """
    return create_visual(
        project_path=project_path,
        page_id=page_id,
        visual_type="card",
        x=x, y=y, width=width, height=height,
        title=title,
        measure_entity=measure_entity,
        measure_property=measure_property
    )


@mcp.tool()
def create_slicer(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    entity: str,
    property: str,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cree un segment (slicer) pour filtrer les donnees.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page cible
        x, y: Position en pixels
        width, height: Dimensions en pixels
        entity: Entite a filtrer
        property: Propriete a filtrer
        title: Titre du slicer (optionnel)

    Returns:
        ID du nouveau visuel
    """
    return create_visual(
        project_path=project_path,
        page_id=page_id,
        visual_type="slicer",
        x=x, y=y, width=width, height=height,
        title=title,
        category_entity=entity,
        category_property=property
    )


# =============================================================================
# TOOLS DE MODIFICATION
# =============================================================================

@mcp.tool()
def update_visual_position(
    project_path: str,
    page_id: str,
    visual_id: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Modifie la position et/ou les dimensions d'un visuel.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        visual_id: ID du visuel
        x, y: Nouvelle position (optionnel)
        width, height: Nouvelles dimensions (optionnel)

    Returns:
        Confirmation de la modification
    """
    return write_report_move_visual(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        x=x,
        y=y,
        width=width,
        height=height,
        dry_run=dry_run,
    )


@mcp.tool()
def update_visual_title(
    project_path: str,
    page_id: str,
    visual_id: str,
    title: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Modifie le titre d'un visuel.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        visual_id: ID du visuel
        title: Nouveau titre

    Returns:
        Confirmation de la modification
    """
    return write_report_update_visual_title(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        title=title,
        dry_run=dry_run,
    )


@mcp.tool()
def update_page_size(
    project_path: str,
    page_id: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Modifie les dimensions d'une page.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        width: Nouvelle largeur (optionnel)
        height: Nouvelle hauteur (optionnel)

    Returns:
        Confirmation de la modification
    """
    return write_report_update_page_size(
        project_path=project_path,
        page_id=page_id,
        width=width,
        height=height,
        dry_run=dry_run,
    )


@mcp.tool()
def rename_page(
    project_path: str,
    page_id: str,
    new_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Renomme une page.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        new_name: Nouveau nom affiche

    Returns:
        Confirmation de la modification
    """
    return write_report_rename_page(
        project_path=project_path,
        page_id=page_id,
        new_name=new_name,
        dry_run=dry_run,
    )


# =============================================================================
# TOOLS DE SUPPRESSION
# =============================================================================

@mcp.tool()
def delete_visual(
    project_path: str,
    page_id: str,
    visual_id: str
) -> Dict[str, Any]:
    """
    Supprime un visuel d'une page.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page
        visual_id: ID du visuel a supprimer

    Returns:
        Confirmation de la suppression
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visual_dir = pages_dir / page_id / "visuals" / visual_id
    if not visual_dir.exists():
        return {"error": f"Visual not found: {visual_id}"}

    shutil.rmtree(visual_dir)

    return {
        "success": True,
        "deleted_visual_id": visual_id,
        "page_id": page_id
    }


@mcp.tool()
def delete_page(
    project_path: str,
    page_id: str
) -> Dict[str, Any]:
    """
    Supprime une page du rapport.

    Args:
        project_path: Chemin vers le dossier du projet
        page_id: ID de la page a supprimer

    Returns:
        Confirmation de la suppression
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    page_dir = pages_dir / page_id
    if not page_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    # Supprimer le dossier de la page
    shutil.rmtree(page_dir)

    # Mettre a jour pages.json
    meta_path = pages_dir / "pages.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    if page_id in meta.get("pageOrder", []):
        meta["pageOrder"].remove(page_id)

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    return {
        "success": True,
        "deleted_page_id": page_id
    }


# =============================================================================
# TOOLS DE COPIE
# =============================================================================

@mcp.tool()
def copy_visual(
    project_path: str,
    source_page_id: str,
    source_visual_id: str,
    target_page_id: str,
    new_x: Optional[int] = None,
    new_y: Optional[int] = None
) -> Dict[str, Any]:
    """
    Copie un visuel vers une autre page (ou la meme page).

    Args:
        project_path: Chemin vers le dossier du projet
        source_page_id: ID de la page source
        source_visual_id: ID du visuel a copier
        target_page_id: ID de la page cible
        new_x: Nouvelle position X (optionnel, garde l'originale si non specifie)
        new_y: Nouvelle position Y (optionnel)

    Returns:
        ID du nouveau visuel cree
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    source_path = pages_dir / source_page_id / "visuals" / source_visual_id / "visual.json"
    if not source_path.exists():
        return {"error": f"Source visual not found: {source_visual_id}"}

    target_visuals_dir = pages_dir / target_page_id / "visuals"
    if not target_visuals_dir.exists():
        return {"error": f"Target page not found: {target_page_id}"}

    # Lire le visuel source
    with open(source_path, 'r', encoding='utf-8') as f:
        visual_data = json.load(f)

    # Generer un nouvel ID
    new_visual_id = PBIIDGenerator.generate()
    visual_data["name"] = new_visual_id

    # Mettre a jour la position si specifie
    if new_x is not None:
        visual_data["position"]["x"] = new_x
    if new_y is not None:
        visual_data["position"]["y"] = new_y

    # Creer le nouveau visuel
    new_visual_dir = target_visuals_dir / new_visual_id
    new_visual_dir.mkdir(parents=True, exist_ok=True)

    with open(new_visual_dir / "visual.json", 'w', encoding='utf-8') as f:
        json.dump(visual_data, f, indent=2)

    return {
        "success": True,
        "new_visual_id": new_visual_id,
        "target_page_id": target_page_id,
        "path": str(new_visual_dir)
    }


@mcp.tool()
def duplicate_page(
    project_path: str,
    source_page_id: str,
    new_display_name: str
) -> Dict[str, Any]:
    """
    Duplique une page avec tous ses visuels.

    Args:
        project_path: Chemin vers le dossier du projet
        source_page_id: ID de la page a dupliquer
        new_display_name: Nom de la nouvelle page

    Returns:
        ID de la nouvelle page
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    source_dir = pages_dir / source_page_id
    if not source_dir.exists():
        return {"error": f"Source page not found: {source_page_id}"}

    # Creer la nouvelle page
    new_page_id = PBIIDGenerator.generate()
    new_page_dir = pages_dir / new_page_id

    # Copier tout le contenu
    shutil.copytree(source_dir, new_page_dir)

    # Mettre a jour page.json avec le nouveau nom et ID
    page_json_path = new_page_dir / "page.json"
    with open(page_json_path, 'r', encoding='utf-8') as f:
        page_data = json.load(f)

    page_data["name"] = new_page_id
    page_data["displayName"] = new_display_name

    with open(page_json_path, 'w', encoding='utf-8') as f:
        json.dump(page_data, f, indent=2)

    # Renommer les IDs des visuels
    visuals_dir = new_page_dir / "visuals"
    if visuals_dir.exists():
        for old_visual_dir in list(visuals_dir.iterdir()):
            if old_visual_dir.is_dir():
                new_visual_id = PBIIDGenerator.generate()
                new_visual_dir = visuals_dir / new_visual_id
                old_visual_dir.rename(new_visual_dir)

                # Mettre a jour le name dans visual.json
                visual_json = new_visual_dir / "visual.json"
                if visual_json.exists():
                    with open(visual_json, 'r', encoding='utf-8') as f:
                        v_data = json.load(f)
                    v_data["name"] = new_visual_id
                    with open(visual_json, 'w', encoding='utf-8') as f:
                        json.dump(v_data, f, indent=2)

    # Ajouter a pages.json
    meta_path = pages_dir / "pages.json"
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)

    meta.setdefault("pageOrder", []).append(new_page_id)

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    return {
        "success": True,
        "new_page_id": new_page_id,
        "displayName": new_display_name,
        "path": str(new_page_dir)
    }


# =============================================================================
# TOOLS BATCH (MODIFICATIONS EN MASSE)
# =============================================================================

@mcp.tool()
def batch_update_visual_titles_by_type(
    project_path: str,
    visual_type: str,
    title_prefix: str
) -> Dict[str, Any]:
    """
    Met a jour les titres de tous les visuels d'un type donne.

    Args:
        project_path: Chemin vers le dossier du projet
        visual_type: Type de visuel a modifier
        title_prefix: Prefixe a ajouter aux titres (sera suivi d'un numero)

    Returns:
        Nombre de visuels modifies
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    modified = []
    counter = 1

    for visual_json in pages_dir.glob("*/visuals/*/visual.json"):
        with open(visual_json, 'r', encoding='utf-8') as f:
            v_data = json.load(f)

        if v_data.get("visual", {}).get("visualType") == visual_type:
            # Mettre a jour le titre
            v_data.setdefault("visual", {}).setdefault("visualContainerObjects", {})
            v_data["visual"]["visualContainerObjects"]["title"] = [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{title_prefix} {counter}'"}}}
                }
            }]

            with open(visual_json, 'w', encoding='utf-8') as f:
                json.dump(v_data, f, indent=2)

            modified.append(str(visual_json))
            counter += 1

    return {
        "success": True,
        "modified_count": len(modified),
        "visual_type": visual_type,
        "modified_files": modified
    }


# =============================================================================
# TEMPLATES DE VISUELS
# =============================================================================

# Configurations de base pour differents types de visuels
VISUAL_TEMPLATES = {
    "barChart": {
        "visualType": "barChart",
        "objects": {
            "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y"}
    },
    "clusteredBarChart": {
        "visualType": "clusteredBarChart",
        "objects": {
            "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y", "Series": "Series"}
    },
    "lineChart": {
        "visualType": "lineChart",
        "objects": {
            "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "dataPoint": [{"properties": {"showMarkers": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y"}
    },
    "areaChart": {
        "visualType": "areaChart",
        "objects": {
            "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y"}
    },
    "pieChart": {
        "visualType": "pieChart",
        "objects": {
            "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y"}
    },
    "donutChart": {
        "visualType": "donutChart",
        "objects": {
            "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Category": "Category", "Y": "Y"}
    },
    "tableEx": {
        "visualType": "tableEx",
        "objects": {
            "grid": [{"properties": {"gridVertical": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Values": "Values"}
    },
    "pivotTable": {
        "visualType": "pivotTable",
        "objects": {},
        "roles": {"Rows": "Rows", "Columns": "Columns", "Values": "Values"}
    },
    "card": {
        "visualType": "card",
        "objects": {
            "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
        },
        "roles": {"Fields": "Fields"}
    },
    "multiRowCard": {
        "visualType": "multiRowCard",
        "objects": {},
        "roles": {"Fields": "Fields"}
    },
    "gauge": {
        "visualType": "gauge",
        "objects": {},
        "roles": {"Y": "Y", "MinValue": "MinValue", "MaxValue": "MaxValue", "TargetValue": "TargetValue"}
    },
    "kpi": {
        "visualType": "kpi",
        "objects": {},
        "roles": {"Indicator": "Indicator", "TrendAxis": "TrendAxis", "Goal": "Goal"}
    }
}


def build_query_state(
    category_entity: Optional[str] = None,
    category_property: Optional[str] = None,
    measure_entity: Optional[str] = None,
    measure_property: Optional[str] = None,
    series_entity: Optional[str] = None,
    series_property: Optional[str] = None,
    additional_measures: Optional[List[Dict]] = None
) -> Dict:
    """Construit le queryState pour un visuel"""
    query_state = {}

    if category_entity and category_property:
        query_state["Category"] = {
            "projections": [{
                "field": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": category_entity}},
                        "Property": category_property
                    }
                },
                "queryRef": f"{category_entity}.{category_property}",
                "nativeQueryRef": category_property
            }]
        }

    if measure_entity and measure_property:
        query_state["Y"] = {
            "projections": [{
                "field": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": measure_entity}},
                        "Property": measure_property
                    }
                },
                "queryRef": f"{measure_entity}.{measure_property}",
                "nativeQueryRef": measure_property
            }]
        }

        # Ajouter des mesures supplementaires
        if additional_measures:
            for m in additional_measures:
                query_state["Y"]["projections"].append({
                    "field": {
                        "Measure": {
                            "Expression": {"SourceRef": {"Entity": m["entity"]}},
                            "Property": m["property"]
                        }
                    },
                    "queryRef": f"{m['entity']}.{m['property']}",
                    "nativeQueryRef": m["property"]
                })

    if series_entity and series_property:
        query_state["Series"] = {
            "projections": [{
                "field": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": series_entity}},
                        "Property": series_property
                    }
                },
                "queryRef": f"{series_entity}.{series_property}",
                "nativeQueryRef": series_property
            }]
        }

    return query_state


@mcp.tool()
def create_bar_chart(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    category_entity: str,
    category_property: str,
    measure_entity: str,
    measure_property: str,
    title: Optional[str] = None,
    stacked: bool = False,
    horizontal: bool = True
) -> Dict[str, Any]:
    """
    Cree un graphique en barres avec configuration complete.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        x, y: Position en pixels
        width, height: Dimensions en pixels
        category_entity: Entite pour les categories (axe)
        category_property: Propriete pour les categories
        measure_entity: Entite pour les valeurs
        measure_property: Mesure pour les valeurs
        title: Titre du graphique
        stacked: True pour barres empilees
        horizontal: True pour barres horizontales (defaut), False pour colonnes verticales

    Returns:
        ID du nouveau visuel
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = PBIIDGenerator.generate()
    visual_dir = visuals_dir / visual_id
    visual_dir.mkdir(parents=True, exist_ok=True)

    # Determiner le type de visuel
    if horizontal:
        visual_type = "clusteredBarChart" if not stacked else "barChart"
    else:
        visual_type = "clusteredColumnChart" if not stacked else "columnChart"

    visual_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": build_query_state(
                    category_entity, category_property,
                    measure_entity, measure_property
                )
            },
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }

    if title:
        visual_config["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                }
            }]
        }

    with open(visual_dir / "visual.json", 'w', encoding='utf-8') as f:
        json.dump(visual_config, f, indent=2)

    return {"success": True, "visual_id": visual_id, "visualType": visual_type}


@mcp.tool()
def create_line_chart(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    category_entity: str,
    category_property: str,
    measure_entity: str,
    measure_property: str,
    title: Optional[str] = None,
    show_markers: bool = True,
    series_entity: Optional[str] = None,
    series_property: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cree un graphique en lignes.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        x, y: Position en pixels
        width, height: Dimensions en pixels
        category_entity: Entite pour l'axe X (souvent une date)
        category_property: Propriete pour l'axe X
        measure_entity: Entite pour les valeurs
        measure_property: Mesure pour les valeurs
        title: Titre du graphique
        show_markers: Afficher les marqueurs sur les points
        series_entity: Entite pour la serie (lignes multiples)
        series_property: Propriete pour la serie

    Returns:
        ID du nouveau visuel
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = PBIIDGenerator.generate()
    visual_dir = visuals_dir / visual_id
    visual_dir.mkdir(parents=True, exist_ok=True)

    visual_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
        "visual": {
            "visualType": "lineChart",
            "query": {
                "queryState": build_query_state(
                    category_entity, category_property,
                    measure_entity, measure_property,
                    series_entity, series_property
                )
            },
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "dataPoint": [{"properties": {"showMarkers": {"expr": {"Literal": {"Value": "true" if show_markers else "false"}}}}}]
            }
        }
    }

    if title:
        visual_config["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                }
            }]
        }

    with open(visual_dir / "visual.json", 'w', encoding='utf-8') as f:
        json.dump(visual_config, f, indent=2)

    return {"success": True, "visual_id": visual_id, "visualType": "lineChart"}


@mcp.tool()
def create_pie_chart(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    category_entity: str,
    category_property: str,
    measure_entity: str,
    measure_property: str,
    title: Optional[str] = None,
    donut: bool = False,
    show_legend: bool = True,
    show_labels: bool = True
) -> Dict[str, Any]:
    """
    Cree un graphique circulaire (camembert ou donut).

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        x, y: Position en pixels
        width, height: Dimensions en pixels
        category_entity: Entite pour les segments
        category_property: Propriete pour les segments
        measure_entity: Entite pour les valeurs
        measure_property: Mesure pour les valeurs
        title: Titre du graphique
        donut: True pour un donut, False pour un camembert
        show_legend: Afficher la legende
        show_labels: Afficher les etiquettes

    Returns:
        ID du nouveau visuel
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = PBIIDGenerator.generate()
    visual_dir = visuals_dir / visual_id
    visual_dir.mkdir(parents=True, exist_ok=True)

    visual_type = "donutChart" if donut else "pieChart"

    visual_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": build_query_state(
                    category_entity, category_property,
                    measure_entity, measure_property
                )
            },
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true" if show_legend else "false"}}}}}],
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true" if show_labels else "false"}}}}}]
            }
        }
    }

    if title:
        visual_config["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                }
            }]
        }

    with open(visual_dir / "visual.json", 'w', encoding='utf-8') as f:
        json.dump(visual_config, f, indent=2)

    return {"success": True, "visual_id": visual_id, "visualType": visual_type}


@mcp.tool()
def create_table(
    project_path: str,
    page_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    columns: List[Dict[str, str]],
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cree un tableau avec plusieurs colonnes.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        x, y: Position en pixels
        width, height: Dimensions en pixels
        columns: Liste de colonnes [{"entity": "Table", "property": "Column", "type": "column|measure"}]
        title: Titre du tableau

    Returns:
        ID du nouveau visuel
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visuals_dir = pages_dir / page_id / "visuals"
    if not visuals_dir.exists():
        return {"error": f"Page not found: {page_id}"}

    visual_id = PBIIDGenerator.generate()
    visual_dir = visuals_dir / visual_id
    visual_dir.mkdir(parents=True, exist_ok=True)

    # Construire les projections pour chaque colonne
    projections = []
    for col in columns:
        field_type = "Column" if col.get("type", "column") == "column" else "Measure"
        projections.append({
            "field": {
                field_type: {
                    "Expression": {"SourceRef": {"Entity": col["entity"]}},
                    "Property": col["property"]
                }
            },
            "queryRef": f"{col['entity']}.{col['property']}",
            "nativeQueryRef": col["property"]
        })

    visual_config = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": visual_id,
        "position": {"x": x, "y": y, "z": 0, "width": width, "height": height},
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {"projections": projections}
                }
            },
            "objects": {
                "grid": [{"properties": {"gridVertical": {"expr": {"Literal": {"Value": "true"}}}}}]
            }
        }
    }

    if title:
        visual_config["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                }
            }]
        }

    with open(visual_dir / "visual.json", 'w', encoding='utf-8') as f:
        json.dump(visual_config, f, indent=2)

    return {"success": True, "visual_id": visual_id, "visualType": "tableEx"}


# =============================================================================
# MODIFICATION JSON GENERIQUE
# =============================================================================

def get_nested_value(obj: Dict, path: str) -> Any:
    """Recupere une valeur imbriquee via un chemin (ex: 'visual.objects.title')"""
    keys = path.split('.')
    current = obj
    for key in keys:
        # Gerer les index de liste [0], [1], etc.
        if '[' in key:
            base_key = key.split('[')[0]
            index = int(key.split('[')[1].rstrip(']'))
            current = current.get(base_key, [])[index]
        else:
            current = current.get(key)
        if current is None:
            return None
    return current


def set_nested_value(obj: Dict, path: str, value: Any) -> None:
    """Definit une valeur imbriquee via un chemin"""
    keys = path.split('.')
    current = obj
    for i, key in enumerate(keys[:-1]):
        if '[' in key:
            base_key = key.split('[')[0]
            index = int(key.split('[')[1].rstrip(']'))
            if base_key not in current:
                current[base_key] = []
            while len(current[base_key]) <= index:
                current[base_key].append({})
            current = current[base_key][index]
        else:
            if key not in current:
                current[key] = {}
            current = current[key]

    # Dernier element
    last_key = keys[-1]
    if '[' in last_key:
        base_key = last_key.split('[')[0]
        index = int(last_key.split('[')[1].rstrip(']'))
        if base_key not in current:
            current[base_key] = []
        while len(current[base_key]) <= index:
            current[base_key].append({})
        current[base_key][index] = value
    else:
        current[last_key] = value


@mcp.tool()
def get_visual_property(
    project_path: str,
    page_id: str,
    visual_id: str,
    property_path: str
) -> Dict[str, Any]:
    """
    Recupere une propriete specifique d'un visuel via son chemin.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel
        property_path: Chemin vers la propriete (ex: "visual.objects.title[0].properties")

    Returns:
        Valeur de la propriete
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visual_path = pages_dir / page_id / "visuals" / visual_id / "visual.json"
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    with open(visual_path, 'r', encoding='utf-8') as f:
        visual_data = json.load(f)

    value = get_nested_value(visual_data, property_path)
    return {"property_path": property_path, "value": value}


@mcp.tool()
def set_visual_property(
    project_path: str,
    page_id: str,
    visual_id: str,
    property_path: str,
    value: Any
) -> Dict[str, Any]:
    """
    Modifie une propriete specifique d'un visuel via son chemin.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel
        property_path: Chemin vers la propriete (ex: "visual.objects.title[0].properties.text")
        value: Nouvelle valeur (sera convertie en structure PBIR si necessaire)

    Returns:
        Confirmation de la modification
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visual_path = pages_dir / page_id / "visuals" / visual_id / "visual.json"
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    with open(visual_path, 'r', encoding='utf-8') as f:
        visual_data = json.load(f)

    set_nested_value(visual_data, property_path, value)

    with open(visual_path, 'w', encoding='utf-8') as f:
        json.dump(visual_data, f, indent=2)

    return {"success": True, "property_path": property_path, "new_value": value}


@mcp.tool()
def update_visual_json(
    project_path: str,
    page_id: str,
    visual_id: str,
    json_patch: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Applique un patch JSON sur un visuel (merge profond).

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel
        json_patch: Dictionnaire a merger avec le visuel existant

    Returns:
        Confirmation de la modification
    """
    return write_report_update_visual_json(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        json_patch=json_patch,
        dry_run=dry_run,
    )


# =============================================================================
# EXTRACTION ET CLONAGE DE STYLE
# =============================================================================

@mcp.tool()
def extract_visual_config(
    project_path: str,
    page_id: str,
    visual_id: str,
    include_query: bool = False,
    include_position: bool = False,
) -> Dict[str, Any]:
    """
    Extrait la configuration d'un visuel (style, formatage, objets).
    Utile pour analyser un visuel existant et reproduire son style.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel
        include_query: Inclure la configuration de donnees
        include_position: Inclure la position

    Returns:
        Configuration extraite du visuel
    """
    return write_report_extract_visual_config(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        include_query=include_query,
        include_position=include_position,
    )


@mcp.tool()
def apply_visual_style(
    project_path: str,
    page_id: str,
    visual_id: str,
    style_config: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Applique une configuration de style a un visuel existant.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel cible
        style_config: Configuration de style (objects, visualContainerObjects)

    Returns:
        Confirmation de la modification
    """
    return write_report_apply_visual_style(
        project_path=project_path,
        page_id=page_id,
        visual_id=visual_id,
        style_config=style_config,
        dry_run=dry_run,
    )


@mcp.tool()
def clone_visual_style(
    project_path: str,
    source_page_id: str,
    source_visual_id: str,
    target_page_id: str,
    target_visual_id: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Clone le style d'un visuel source vers un visuel cible.
    Copie les objets de formatage mais pas les donnees.

    Args:
        project_path: Chemin vers le projet
        source_page_id: ID de la page source
        source_visual_id: ID du visuel source
        target_page_id: ID de la page cible
        target_visual_id: ID du visuel cible

    Returns:
        Confirmation de la modification
    """
    return write_report_clone_visual_style(
        project_path=project_path,
        source_page_id=source_page_id,
        source_visual_id=source_visual_id,
        target_page_id=target_page_id,
        target_visual_id=target_visual_id,
        dry_run=dry_run,
    )


@mcp.tool()
def list_visual_properties(
    project_path: str,
    page_id: str,
    visual_id: str
) -> Dict[str, Any]:
    """
    Liste toutes les proprietes configurees d'un visuel.
    Utile pour decouvrir les proprietes disponibles.

    Args:
        project_path: Chemin vers le projet
        page_id: ID de la page
        visual_id: ID du visuel

    Returns:
        Liste des proprietes avec leurs chemins
    """
    pages_dir = get_pages_dir(project_path)
    if not pages_dir:
        return {"error": "Pages directory not found"}

    visual_path = pages_dir / page_id / "visuals" / visual_id / "visual.json"
    if not visual_path.exists():
        return {"error": f"Visual not found: {visual_id}"}

    with open(visual_path, 'r', encoding='utf-8') as f:
        visual_data = json.load(f)

    def extract_paths(obj: Any, prefix: str = "") -> List[str]:
        """Extrait tous les chemins de proprietes"""
        paths = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (dict, list)):
                    paths.extend(extract_paths(value, new_prefix))
                else:
                    paths.append(f"{new_prefix} = {value}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_prefix = f"{prefix}[{i}]"
                paths.extend(extract_paths(item, new_prefix))
        return paths

    properties = extract_paths(visual_data)

    return {
        "visual_id": visual_id,
        "visualType": visual_data.get("visual", {}).get("visualType"),
        "properties": properties,
        "count": len(properties)
    }


# =============================================================================
# SEMANTIC MODEL (TMDL) - LECTURE SEULE POUR L'INSTANT
# =============================================================================

@mcp.tool()
def model_get_summary(project_path: str) -> Dict[str, Any]:
    """
    Retourne un resume structure du modele semantique.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Metadonnees du modele, tables, roles, mesures et relations
    """
    return read_model_get_summary(project_path)


@mcp.tool()
def model_list_tables(project_path: str) -> Dict[str, Any]:
    """
    Liste les tables du modele semantique.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Liste des tables avec leurs fichiers TMDL
    """
    return read_model_list_tables(project_path)


@mcp.tool()
def model_list_relationships(project_path: str) -> Dict[str, Any]:
    """
    Liste les relations du modele semantique.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Relations du modele avec cardinalite et filtrage
    """
    return read_model_list_relationships(project_path)


@mcp.tool()
def model_list_measures(project_path: str) -> Dict[str, Any]:
    """
    Liste les mesures du modele semantique.

    Args:
        project_path: Chemin vers le dossier du projet

    Returns:
        Catalogue des mesures avec expressions et dossiers d'affichage
    """
    return read_model_list_measures(project_path)


@mcp.tool()
def model_upsert_measure(
    project_path: str,
    table_name: str,
    measure_name: str,
    expression: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree ou met a jour une mesure dans une table TMDL locale.

    Args:
        project_path: Chemin vers le dossier du projet
        table_name: Nom de la table cible
        measure_name: Nom de la mesure
        expression: Expression DAX de la mesure
        dry_run: Simule l'ecriture sans modifier les fichiers

    Returns:
        Confirmation de la mutation ou details de simulation
    """
    return write_model_upsert_measure(
        project_path=project_path,
        table_name=table_name,
        measure_name=measure_name,
        expression=expression,
        dry_run=dry_run,
    )


@mcp.tool()
def model_create_relationship(
    project_path: str,
    relationship_name: str,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree ou met a jour une relation TMDL locale.

    Args:
        project_path: Chemin vers le dossier du projet
        relationship_name: Nom de la relation
        from_table: Table source
        from_column: Colonne source
        to_table: Table cible
        to_column: Colonne cible
        dry_run: Simule l'ecriture sans modifier les fichiers

    Returns:
        Confirmation de la mutation ou details de simulation
    """
    return write_model_create_relationship(
        project_path=project_path,
        relationship_name=relationship_name,
        from_table=from_table,
        from_column=from_column,
        to_table=to_table,
        to_column=to_column,
        dry_run=dry_run,
    )


@mcp.tool()
def model_update_table_description(
    project_path: str,
    table_name: str,
    description: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree ou met a jour la description d'une table TMDL locale.
    """
    return write_model_update_table_description(
        project_path=project_path,
        table_name=table_name,
        description=description,
        dry_run=dry_run,
    )


@mcp.tool()
def model_update_column_metadata(
    project_path: str,
    table_name: str,
    column_name: str,
    description: Optional[str] = None,
    summarize_by: Optional[str] = None,
    format_string: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree ou met a jour des metadonnees de colonne TMDL locale.
    """
    return write_model_update_column_metadata(
        project_path=project_path,
        table_name=table_name,
        column_name=column_name,
        description=description,
        summarize_by=summarize_by,
        format_string=format_string,
        dry_run=dry_run,
    )


@mcp.tool()
def model_upsert_role(
    project_path: str,
    role_name: str,
    table_name: str,
    dax_filter_expression: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree ou met a jour un role TMDL local.
    """
    return write_model_upsert_role(
        project_path=project_path,
        role_name=role_name,
        table_name=table_name,
        dax_filter_expression=dax_filter_expression,
        dry_run=dry_run,
    )


@mcp.tool()
def model_create_table(
    project_path: str,
    table_name: str,
    columns: List[Dict[str, str]],
    source_expression: str,
    query_group: str = "DataModel",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Cree une nouvelle table TMDL locale avec ses colonnes et sa partition Power Query.

    Args:
        project_path: Chemin vers le dossier du projet
        table_name: Nom de la table a creer
        columns: Liste de colonnes [{"name": "Col1", "dataType": "string"}]
        source_expression: Expression M (Power Query) de connexion a la source
        query_group: Groupe de requetes (defaut: "DataModel")
        dry_run: Si True, simule l'operation sans ecrire de fichiers (defaut: False)
    """
    return write_model_create_table(
        project_path=project_path,
        table_name=table_name,
        columns=columns,
        source_expression=source_expression,
        query_group=query_group,
        dry_run=dry_run,
    )


@mcp.tool()
def report_create_from_datasource_spec(
    project_path: str,
    table_name: str,
    columns: List[Dict[str, str]],
    source_expression: str,
    query_group: str = "DataModel",
    measures: Optional[List[Dict[str, str]]] = None,
    page_name: str = "Analysis",
    visuals_spec: Optional[List[Dict[str, Any]]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Pipeline de bout en bout : cree une table TMDL, ses mesures DAX, une page de rapport, et des visuels configurés.
    Le projet est valide a la fin.

    Args:
        project_path: Chemin vers le dossier du projet
        table_name: Nom de la table a creer
        columns: Liste de colonnes [{"name": "Col1", "dataType": "string"}]
        source_expression: Expression M (Power Query) source
        query_group: Groupe de requete (defaut: "DataModel")
        measures: Liste de mesures a creer [{"name": "M1", "expression": "SUM(...)"}] (optionnel)
        page_name: Nom de la page de rapport a creer (defaut: "Analysis")
        visuals_spec: Liste de visuels a creer (optionnel)
        dry_run: Si True, simule l'operation sans modifier de fichiers (defaut: True)
    """
    return write_report_create_from_datasource_spec(
        project_path=project_path,
        table_name=table_name,
        columns=columns,
        source_expression=source_expression,
        query_group=query_group,
        measures=measures,
        page_name=page_name,
        visuals_spec=visuals_spec,
        dry_run=dry_run,
    )


@mcp.tool()
def list_tables(project_path: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `model_list_tables`."""
    return read_model_list_tables(project_path)


@mcp.tool()
def get_table_content(project_path: str, table_name: str) -> Dict[str, Any]:
    """Compatibilite legacy vers `powerbi_mcp.model.read.get_table_content`."""
    return model_get_table_content(project_path, table_name)


# =============================================================================
# VALIDATION TOOLS
# =============================================================================

def _filter_by_severity(report, severity_threshold: str):
    """Filter issues to those at or above the threshold (info < warning < error)."""
    order = {"info": 0, "warning": 1, "error": 2}
    threshold_level = order.get(severity_threshold, 0)
    if threshold_level == 0:
        return report
    filtered_issues = [i for i in report.issues if order.get(i.severity, 0) >= threshold_level]
    has_errors = any(i.severity == "error" for i in filtered_issues)
    return ValidationReport(ok=not has_errors, issues=filtered_issues)


@mcp.tool()
def project_validate(project_path: str, severity_threshold: str = "error") -> dict:
    """Validate the full PBIP project: PBIR JSON schemas, TMDL rules, and report-to-model reachability."""
    report = validate_project(project_path)
    filtered = _filter_by_severity(report, severity_threshold)
    return filtered.to_dict()


@mcp.tool()
def report_validate(project_path: str, severity_threshold: str = "error") -> dict:
    """Validate all PBIR JSON files in the report against Microsoft schemas."""
    report = validate_report(project_path)
    filtered = _filter_by_severity(report, severity_threshold)
    return filtered.to_dict()


@mcp.tool()
def model_validate(project_path: str, severity_threshold: str = "error") -> dict:
    """Validate TMDL files: reference integrity, uniqueness, naming, and cross-file coherence."""
    report = validate_model(project_path)
    filtered = _filter_by_severity(report, severity_threshold)
    return filtered.to_dict()


# =============================================================================
# POINT D'ENTREE
# =============================================================================

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="powerbi-mcp-server",
        description="Run the local Power BI MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to use. Defaults to stdio for local MCP clients.",
    )
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Optional mount path passed to FastMCP for HTTP transports.",
    )
    args = parser.parse_args(argv)
    mcp.run(transport=args.transport, mount_path=args.mount_path)

if __name__ == "__main__":
    main()

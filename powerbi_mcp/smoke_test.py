"""
Smoke test for the extracted Power BI MCP modules.

The script validates the read paths against the checked-in example fixture,
then exercises one real write path against a repo-local copy of that fixture.
"""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from powerbi_mcp.analysis.bindings import report_get_visual_bindings
from powerbi_mcp.model.read import model_list_measures, model_list_tables
from powerbi_mcp.report.read import project_get_summary, report_list_pages, report_list_visuals
from powerbi_mcp.report.write import report_create_page
from powerbi_mcp.visual_ai.critic import report_design_audit
from powerbi_mcp.visual_ai.examples import (
    custom_visual_eligibility,
    visual_role_examples,
    visual_template_library,
)
from powerbi_mcp.visual_ai.layout import page_layout_recommend
from powerbi_mcp.visual_ai.qa_loop import run_file_first_visual_qa_loop
from powerbi_mcp.visual_ai.readiness import report_design_readiness_check
from powerbi_mcp.visual_ai.studio import report_design_studio_plan
from powerbi_mcp.visual_ai.workbench import (
    page_design_apply_quick_wins,
    page_layout_apply_quick_wins,
    page_layout_apply_reflow_plan,
)


FIXTURE_PROJECT_PATH = REPO_ROOT / "example"
TEMP_ROOT = Path("C:/_pbimcp_smoke")
EXTERNAL_FOCUS_PROJECT_PATHS = (
    Path("C:/Users/DavidBru/FIVEFORTY/Documents/_WORK/540/Interne/PBI"),
    Path("/mnt/c/Users/DavidBru/FIVEFORTY/Documents/_WORK/540/Interne/PBI"),
)


def _make_fixture_copy() -> Path:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
    shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
    return project_dir


def _cleanup_temp_root() -> None:
    if TEMP_ROOT.exists() and not any(TEMP_ROOT.iterdir()):
        TEMP_ROOT.rmdir()


def _focus_project_path() -> Path:
    for candidate in EXTERNAL_FOCUS_PROJECT_PATHS:
        if candidate.exists():
            return candidate
    return FIXTURE_PROJECT_PATH


def _find_visual_with_bindings(project_path: str) -> tuple[dict, dict, dict]:
    pages_result = report_list_pages(project_path)
    for page in pages_result["pages"]:
        visuals_result = report_list_visuals(project_path, page["id"])
        for visual in visuals_result["visuals"]:
            bindings_result = report_get_visual_bindings(project_path, page["id"], visual["id"])
            if bindings_result.get("count", 0) > 0:
                return page, visual, bindings_result
    raise RuntimeError("No visual with query-state bindings found in fixture")


def run_test() -> bool:
    fixture_path = str(FIXTURE_PROJECT_PATH)
    print("=" * 60)
    print("SMOKE TEST - Power BI MCP Server")
    print("=" * 60)
    print(f"Fixture path: {fixture_path}")
    print()

    print("1. Testing project_get_summary()...")
    summary = project_get_summary(fixture_path)
    if "error" in summary:
        print(f"   FAIL: {summary['error']}")
        return False
    print(f"   Report dir: {summary['report_dir']}")
    print(f"   Model dir: {summary['model_dir']}")
    print(f"   Pages: {summary['page_count']}, Visuals: {summary['visual_count']}, Tables: {summary['table_count']}")
    print("   OK")
    print()

    print("2. Testing report_list_pages()...")
    pages_result = report_list_pages(fixture_path)
    if "error" in pages_result:
        print(f"   FAIL: {pages_result['error']}")
        return False
    if pages_result["count"] == 0:
        print("   FAIL: fixture report has no pages")
        return False
    print(f"   Found {pages_result['count']} pages:")
    for page in pages_result["pages"][:3]:
        print(f"   - {page['displayName']} ({page['visual_count']} visuals)")
    if pages_result["count"] > 3:
        print(f"   ... and {pages_result['count'] - 3} more")
    print("   OK")
    print()

    print("3. Testing report_list_visuals()...")
    first_page = pages_result["pages"][0]
    visuals_result = report_list_visuals(fixture_path, first_page["id"])
    if "error" in visuals_result:
        print(f"   FAIL: {visuals_result['error']}")
        return False
    print(f"   Found {visuals_result['count']} visuals on '{first_page['displayName']}':")
    for visual in visuals_result["visuals"][:3]:
        title = visual["title"] or "(no title)"
        print(f"   - {visual['visualType']}: {title}")
    print("   OK")
    print()

    print("4. Testing model_list_tables() and model_list_measures()...")
    tables_result = model_list_tables(fixture_path)
    measures_result = model_list_measures(fixture_path)
    if "error" in tables_result:
        print(f"   FAIL: {tables_result['error']}")
        return False
    if "error" in measures_result:
        print(f"   FAIL: {measures_result['error']}")
        return False
    print(f"   Tables: {tables_result['count']}")
    print(f"   Measures: {measures_result['count']}")
    print("   OK")
    print()

    print("5. Testing report_get_visual_bindings()...")
    page, visual, bindings_result = _find_visual_with_bindings(fixture_path)
    print(f"   Found bindings on visual '{visual['id']}' ({visual['visualType']}) in page '{page['displayName']}'")
    print(f"   Binding count: {bindings_result['count']}")
    print("   OK")
    print()

    print("6. Testing one real write path on a copied fixture...")
    copied_project_path = _make_fixture_copy()
    try:
        before_pages = report_list_pages(str(copied_project_path))
        if "error" in before_pages:
            print(f"   FAIL: {before_pages['error']}")
            return False
        write_result = report_create_page(str(copied_project_path), "Smoke Test Page")
        if "error" in write_result:
            print(f"   FAIL: {write_result['error']}")
            return False
        copied_pages = report_list_pages(str(copied_project_path))
        if "error" in copied_pages:
            print(f"   FAIL: {copied_pages['error']}")
            return False
        created_page_ids = {page["id"] for page in copied_pages["pages"]}
        if copied_pages["count"] != before_pages["count"] + 1:
            print("   FAIL: page count did not increase after report_create_page()")
            return False
        if write_result["page_id"] not in created_page_ids:
            print("   FAIL: created page is not discoverable through report_list_pages()")
            return False
        print(f"   Created page '{write_result['displayName']}' with id {write_result['page_id']}")
        print(f"   Copied fixture now has {copied_pages['count']} pages")
        print("   OK")
    finally:
        shutil.rmtree(copied_project_path, ignore_errors=True)
        _cleanup_temp_root()
    print()

    print("7. Testing validate_project() on fixture...")
    from powerbi_mcp.validation.engine import validate_project
    val_report = validate_project(fixture_path)
    errors = val_report.errors()
    warnings = val_report.warnings()
    assert val_report.ok, f"validate_project returned ok=False. Errors: {errors}"
    print(f"   {len(errors)} errors, {len(warnings)} warnings")
    print("   OK")
    print()

    print("8. Testing report_design_audit()...")
    design_audit = report_design_audit(
        fixture_path,
        audience="executive",
        intent="monitor consulting performance",
    )
    if "error" in design_audit:
        print(f"   FAIL: {design_audit['error']}")
        return False
    if design_audit["page_count"] == 0 or not design_audit["findings"]:
        print("   FAIL: design audit did not inspect the fixture report")
        return False
    print(f"   Score: {design_audit['score']} ({design_audit['grade']})")
    print(f"   Findings: {len(design_audit['findings'])}")
    print("   OK")
    print()

    print("9. Testing page_design_apply_quick_wins() dry-run...")
    quick_wins = page_design_apply_quick_wins(
        fixture_path,
        first_page["id"],
        audience="executive",
        intent="monitor consulting performance",
        max_actions=1,
    )
    if "error" in quick_wins:
        print(f"   FAIL: {quick_wins['error']}")
        return False
    if not quick_wins["success"] or not quick_wins["dry_run"] or quick_wins["attempted_count"] == 0:
        print("   FAIL: design quick wins did not produce a safe dry-run action")
        return False
    print(f"   Attempted: {quick_wins['attempted_count']}")
    print(f"   Applied: {quick_wins['applied_count']} (dry-run)")
    print("   OK")
    print()

    print("10. Testing page_layout_apply_quick_wins() dry-run...")
    layout_quick_wins = page_layout_apply_quick_wins(
        fixture_path,
        first_page["id"],
        grid_size=8,
        max_actions=1,
    )
    if "error" in layout_quick_wins:
        print(f"   FAIL: {layout_quick_wins['error']}")
        return False
    if (
        not layout_quick_wins["success"]
        or not layout_quick_wins["dry_run"]
        or layout_quick_wins["attempted_count"] == 0
    ):
        print("   FAIL: layout quick wins did not produce a safe dry-run action")
        return False
    print(f"   Attempted: {layout_quick_wins['attempted_count']}")
    print(f"   Applied: {layout_quick_wins['applied_count']} (dry-run)")
    print("   OK")
    print()

    print("11. Testing page_layout_recommend()...")
    layout_recommendation = page_layout_recommend(
        fixture_path,
        first_page["id"],
        audience="executive",
        intent="overview of consulting performance",
    )
    if "error" in layout_recommendation:
        print(f"   FAIL: {layout_recommendation['error']}")
        return False
    if not layout_recommendation["recommendations"] or layout_recommendation["mutates_files"]:
        print("   FAIL: layout recommendation did not return read-only guidance")
        return False
    print(f"   Blueprint: {layout_recommendation['blueprint']['page_archetype']}")
    print(f"   Recommendations: {layout_recommendation['recommendation_count']}")
    print("   OK")
    print()

    print("12. Testing page_layout_apply_reflow_plan() dry-run...")
    reflow = page_layout_apply_reflow_plan(
        fixture_path,
        first_page["id"],
        audience="executive",
        intent="overview of consulting performance",
        max_moves=1,
    )
    if "error" in reflow:
        print(f"   FAIL: {reflow['error']}")
        return False
    if not reflow["success"] or not reflow["dry_run"] or reflow["attempted_count"] == 0:
        print("   FAIL: reflow plan did not produce a safe dry-run move")
        return False
    print(f"   Attempted: {reflow['attempted_count']}")
    print(f"   Applied: {reflow['applied_count']} (dry-run)")
    print("   OK")
    print()

    print("13. Testing report_design_studio_plan()...")
    studio_plan = report_design_studio_plan(
        fixture_path,
        audience="executive",
        intent="overview of consulting performance",
        page_limit=1,
    )
    if "error" in studio_plan:
        print(f"   FAIL: {studio_plan['error']}")
        return False
    if studio_plan["mutates_files"] or not studio_plan["page_studies"]:
        print("   FAIL: studio plan did not produce read-only page studies")
        return False
    print(f"   Maturity: {studio_plan['maturity']}")
    print(f"   Actions: {studio_plan['action_summary']['total_actions']}")
    print("   OK")
    print()

    print("14. Testing report_design_readiness_check()...")
    readiness = report_design_readiness_check(
        fixture_path,
        audience="executive",
        intent="overview of consulting performance",
        page_limit=1,
    )
    if "error" in readiness:
        print(f"   FAIL: {readiness['error']}")
        return False
    if readiness["status"] != "mvp-ready" or not readiness["validation"]["ok"]:
        print("   FAIL: readiness check did not report the fixture as MVP ready")
        return False
    print(f"   Status: {readiness['status']}")
    print(f"   Score: {readiness['readiness_score']}")
    print("   OK")
    print()

    print("15. Testing run_file_first_visual_qa_loop()...")
    visual_qa_dir = TEMP_ROOT / "visual-qa"
    visual_qa = run_file_first_visual_qa_loop(
        str(REPO_ROOT),
        audience="executive",
        intent="overview of consulting performance",
        output_dir=str(visual_qa_dir),
        page_limit=1,
    )
    try:
        if visual_qa["status"] != "passed" or visual_qa["project_count"] != 1:
            print("   FAIL: visual QA loop did not pass on the fixture project")
            return False
        if not Path(visual_qa["report_file"]).exists():
            print("   FAIL: visual QA loop did not write a report file")
            return False
        print(f"   Projects: {visual_qa['project_count']}")
        print(f"   Report: {visual_qa['report_file']}")
        print("   OK")
    finally:
        shutil.rmtree(visual_qa_dir, ignore_errors=True)
        _cleanup_temp_root()
    print()

    print("16. Testing Focus-derived visual template intelligence...")
    focus_project_path = _focus_project_path()
    template_library = visual_template_library(str(focus_project_path), supported_only=True)
    if "error" in template_library:
        print(f"   FAIL: {template_library['error']}")
        return False
    if not template_library["templates_by_type"]:
        print("   FAIL: visual template library is empty")
        return False
    if "lineChart" not in template_library["templates_by_type"]:
        print("   FAIL: visual template library did not include lineChart examples")
        return False

    role_examples = visual_role_examples(str(focus_project_path), visual_type="pivotTable")
    if "error" in role_examples:
        print(f"   FAIL: {role_examples['error']}")
        return False
    required_pivot_roles = {"Rows", "Columns", "Values"}
    if focus_project_path != FIXTURE_PROJECT_PATH and not required_pivot_roles.issubset(role_examples["roles"]):
        print("   FAIL: Focus pivotTable examples did not expose Rows, Columns and Values roles")
        return False

    custom_visuals = custom_visual_eligibility(str(focus_project_path))
    if "error" in custom_visuals:
        print(f"   FAIL: {custom_visuals['error']}")
        return False
    if focus_project_path != FIXTURE_PROJECT_PATH:
        custom_names = {visual["name"] for visual in custom_visuals["custom_visuals"]}
        if not {"CalendarVisual", "WordCloud", "textFilter"}.issubset(custom_names):
            print("   FAIL: Focus custom visual eligibility missed expected custom visuals")
            return False
        print(f"   Custom visuals: {custom_visuals['count']}")
    else:
        print("   External Focus project not available; custom visual eligibility checked on fixture fallback")
    print(f"   Template types: {template_library['visual_type_count']}")
    print(f"   Pivot roles: {', '.join(sorted(role_examples['roles'])) or '(none)'}")
    print("   OK")
    print()

    print("=" * 60)
    print("ALL SMOKE TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)

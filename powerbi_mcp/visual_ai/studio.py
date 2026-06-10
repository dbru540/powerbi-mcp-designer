from typing import Any

from powerbi_mcp.visual_ai.critic import report_design_audit
from powerbi_mcp.visual_ai.layout import page_layout_recommend, page_layout_reflow_plan
from powerbi_mcp.visual_ai.workbench import page_design_action_plan, page_layout_action_plan


def _maturity(score: float) -> str:
    if score >= 4.5:
        return "excellent"
    if score >= 3.8:
        return "strong"
    if score >= 2.5:
        return "needs-improvement"
    return "weak"


def report_design_studio_plan(
    project_path: str,
    audience: str,
    intent: str,
    subject: str | None = None,
    page_limit: int = 3,
    visual_qa_report_file: str | None = None,
) -> dict[str, Any]:
    audit = report_design_audit(
        project_path,
        audience=audience,
        intent=intent,
        visual_qa_report_file=visual_qa_report_file,
    )
    if "error" in audit:
        return audit

    selected_pages = audit["page_audits"][:page_limit]
    page_studies = []
    total_title_actions = 0
    total_layout_snap_actions = 0
    total_reflow_actions = 0
    for page_audit in selected_pages:
        page_id = page_audit["page_id"]
        title_plan = page_design_action_plan(
            project_path,
            page_id,
            audience=audience,
            intent=intent,
        )
        layout_snap_plan = page_layout_action_plan(project_path, page_id)
        layout_recommendation = page_layout_recommend(
            project_path,
            page_id,
            audience=audience,
            intent=intent,
            subject=subject,
        )
        reflow_plan = page_layout_reflow_plan(
            project_path,
            page_id,
            audience=audience,
            intent=intent,
            subject=subject,
        )

        title_actions = title_plan.get("actions", [])
        layout_snap_actions = layout_snap_plan.get("actions", [])
        reflow_actions = reflow_plan.get("actions", [])
        total_title_actions += len(title_actions)
        total_layout_snap_actions += len(layout_snap_actions)
        total_reflow_actions += len(reflow_actions)
        page_studies.append(
            {
                "page_id": page_id,
                "page_name": page_audit["page_name"],
                "audit_score": page_audit["score"],
                "audit_grade": page_audit["grade"],
                "layout_recommendation": layout_recommendation,
                "title_actions": title_actions,
                "layout_snap_actions": layout_snap_actions,
                "reflow_actions": reflow_actions,
            }
        )

    total_actions = total_title_actions + total_layout_snap_actions + total_reflow_actions
    visual_evidence_gate = audit.get("visual_evidence_gate")
    if visual_evidence_gate is None:
        critique_mode = "file-first"
        critique_guidance = "Use file-first PBIR metadata critique; no Desktop screenshot evidence was supplied."
    elif visual_evidence_gate.get("screenshot_based_critique_allowed"):
        critique_mode = "screenshot-informed"
        critique_guidance = "Desktop evidence is ready; screenshot-informed visual critique is allowed."
    else:
        critique_mode = "file-first-only"
        critique_guidance = "Desktop evidence is not ready; use file-first critique only and recapture before screenshot-based critique."

    return {
        "project_path": project_path,
        "audience": audience,
        "intent": intent,
        "subject": subject,
        "mutates_files": False,
        "critique_mode": critique_mode,
        "critique_guidance": critique_guidance,
        "visual_evidence_gate": visual_evidence_gate,
        "evidence_findings": audit.get("evidence_findings", []),
        "report_score": audit["score"],
        "maturity": _maturity(float(audit["score"])),
        "report_audit": audit,
        "page_studies": page_studies,
        "action_summary": {
            "title_actions": total_title_actions,
            "layout_snap_actions": total_layout_snap_actions,
            "reflow_actions": total_reflow_actions,
            "total_actions": total_actions,
        },
        "execution_sequence": [
            {
                "step": "audit",
                "tool": "report_design_audit",
                "dry_run_default": True,
                "purpose": "Understand design quality before changing files.",
            },
            {
                "step": "quick_titles",
                "tool": "page_design_apply_quick_wins",
                "dry_run_default": True,
                "purpose": "Add missing titles to bound visuals.",
            },
            {
                "step": "grid_snap",
                "tool": "page_layout_apply_quick_wins",
                "dry_run_default": True,
                "purpose": "Normalize visual alignment without semantic changes.",
            },
            {
                "step": "reviewed_reflow",
                "tool": "page_layout_apply_reflow_plan",
                "dry_run_default": True,
                "purpose": "Move existing visuals toward the selected audience blueprint.",
            },
        ],
    }

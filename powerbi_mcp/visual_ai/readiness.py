from typing import Any

from powerbi_mcp.validation.engine import validate_project
from powerbi_mcp.visual_ai.studio import report_design_studio_plan


def _capability(name: str, ready: bool, evidence: str, limit: str | None = None) -> dict[str, Any]:
    return {
        "capability": name,
        "ready": ready,
        "evidence": evidence,
        "limit": limit,
    }


def report_design_readiness_check(
    project_path: str,
    audience: str,
    intent: str,
    subject: str | None = None,
    page_limit: int = 1,
) -> dict[str, Any]:
    validation = validate_project(project_path).to_dict()
    if not validation["ok"]:
        return {
            "project_path": project_path,
            "audience": audience,
            "intent": intent,
            "subject": subject,
            "mutates_files": False,
            "status": "blocked",
            "readiness_score": 0.2,
            "validation": validation,
            "capabilities": [],
            "remaining_gates": [
                {
                    "gate": "project_validation",
                    "severity": "blocking",
                    "reason": "Project validation errors must be fixed before design automation is safe.",
                }
            ],
            "recommended_entrypoint": "project_validate",
        }

    studio = report_design_studio_plan(
        project_path,
        audience=audience,
        intent=intent,
        subject=subject,
        page_limit=page_limit,
    )
    if "error" in studio:
        return {
            "project_path": project_path,
            "audience": audience,
            "intent": intent,
            "subject": subject,
            "mutates_files": False,
            "status": "blocked",
            "readiness_score": 0.35,
            "validation": validation,
            "error": studio["error"],
            "capabilities": [],
            "remaining_gates": [
                {
                    "gate": "studio_plan",
                    "severity": "blocking",
                    "reason": studio["error"],
                }
            ],
            "recommended_entrypoint": "report_design_studio_plan",
        }

    capabilities = [
        _capability(
            "report_design_audit",
            True,
            f"Studio audit returned maturity {studio['maturity']} with report score {studio['report_score']}.",
        ),
        _capability(
            "report_design_studio_plan",
            True,
            f"Studio produced {len(studio['page_studies'])} page studies.",
        ),
        _capability(
            "title_quick_wins",
            True,
            f"{studio['action_summary']['title_actions']} candidate title actions found.",
        ),
        _capability(
            "layout_snap_quick_wins",
            True,
            f"{studio['action_summary']['layout_snap_actions']} candidate grid snap actions found.",
        ),
        _capability(
            "reviewed_reflow",
            True,
            f"{studio['action_summary']['reflow_actions']} candidate reflow actions found.",
            "Dry-run and human/visual review remain required before broad application.",
        ),
        _capability(
            "native_visual_generation",
            True,
            "Native visual plan generation and application exist through visual_plan_generate_and_apply.",
            "Generation is limited to supported native PBIR families and known role mappings.",
        ),
    ]
    remaining_gates = [
        {
            "gate": "visual_qa",
            "severity": "production",
            "reason": "No automated Power BI Desktop or screenshot comparison loop is available yet.",
        },
        {
            "gate": "full_apply_orchestration",
            "severity": "production",
            "reason": "Studio remains read-only by design; broad apply should wait for visual QA.",
        },
        {
            "gate": "custom_visual_generation",
            "severity": "future",
            "reason": "Deneb/custom visual generation needs manifest/capability-aware implementation.",
        },
    ]
    return {
        "project_path": project_path,
        "audience": audience,
        "intent": intent,
        "subject": subject,
        "mutates_files": False,
        "status": "mvp-ready",
        "readiness_score": 0.82,
        "validation": validation,
        "studio": studio,
        "capabilities": capabilities,
        "remaining_gates": remaining_gates,
        "recommended_entrypoint": "report_design_studio_plan -> dry-run apply tools -> visual review",
    }

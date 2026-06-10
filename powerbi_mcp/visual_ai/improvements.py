from typing import Any

from powerbi_mcp.visual_ai.critic import page_design_audit, report_design_audit


def _bucket_findings(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    quick_wins = []
    structural = []
    manual_review = []

    for finding in findings:
        action = {
            "dimension": finding["dimension"],
            "severity": finding["severity"],
            "recommendation": finding["recommendation"],
            "evidence": finding["evidence"],
            "page_id": finding.get("page_id"),
            "visual_id": finding.get("visual_id"),
            "visual_type": finding.get("visual_type"),
        }
        if finding["dimension"] in {"title clarity", "visual type fit"}:
            quick_wins.append(action)
        elif finding["dimension"] in {"density", "layout balance", "visual hierarchy"}:
            structural.append(action)
        else:
            manual_review.append(action)

    return {
        "quick_wins": quick_wins,
        "structural_recommendations": structural,
        "manual_review": manual_review,
    }


def page_design_improve_plan(
    project_path: str,
    page_id: str,
    audience: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    audit = page_design_audit(project_path, page_id, audience, intent)
    if "error" in audit:
        return audit

    buckets = _bucket_findings(audit["findings"])
    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": audit["page_name"],
        "audience": audience,
        "intent": intent,
        "audit_score": audit["score"],
        "audit_grade": audit["grade"],
        "mutates_files": False,
        **buckets,
    }


def report_design_improve_plan(
    project_path: str,
    audience: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    audit = report_design_audit(project_path, audience, intent)
    if "error" in audit:
        return audit

    page_plans = []
    all_findings = []
    for page_audit in audit["page_audits"]:
        all_findings.extend(page_audit["findings"])
        page_plans.append(
            page_design_improve_plan(project_path, page_audit["page_id"], audience, intent)
        )

    buckets = _bucket_findings(all_findings)
    return {
        "project_path": project_path,
        "audience": audience,
        "intent": intent,
        "page_count": audit["page_count"],
        "audit_score": audit["score"],
        "audit_grade": audit["grade"],
        "page_plans": page_plans,
        "mutates_files": False,
        **buckets,
    }

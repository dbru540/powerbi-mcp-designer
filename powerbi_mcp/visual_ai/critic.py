from typing import Any

from powerbi_mcp.analysis.bindings import report_get_visual_bindings
from powerbi_mcp.report.read import report_get_visual, report_list_pages, report_list_visuals
from powerbi_mcp.visual_ai.desktop_evidence import report_design_desktop_evidence_summary
from powerbi_mcp.visual_ai.rubric import build_finding, summarize_scores
from powerbi_mcp.visual_ai.vocabulary import visual_vocabulary_classify


def _page_density_finding(page: dict[str, Any]) -> dict[str, Any]:
    count = int(page.get("visual_count", 0))
    if count > 14:
        return build_finding(
            "density",
            "warning",
            2.0,
            f"Page has {count} visuals, which creates competing focal points.",
            "Group the page into clearer zones and remove or move supporting detail.",
            page_id=page.get("id"),
            page_name=page.get("displayName"),
        )
    if count < 3:
        return build_finding(
            "density",
            "info",
            3.2,
            f"Page has only {count} visuals.",
            "Confirm the page has enough context for its audience.",
            page_id=page.get("id"),
            page_name=page.get("displayName"),
        )
    return build_finding(
        "density",
        "info",
        4.2,
        f"Page has {count} visuals.",
        "Keep the visual count controlled and preserve a clear focal path.",
        page_id=page.get("id"),
        page_name=page.get("displayName"),
    )


def _visual_type_finding(
    visual: dict[str, Any],
    vocabulary: dict[str, Any],
    *,
    page_id: str,
) -> dict[str, Any]:
    visual_type = visual.get("visualType", "unknown")
    recommended = vocabulary.get("recommended_visual_families", [])
    if visual_type in recommended:
        return build_finding(
            "visual type fit",
            "info",
            4.2,
            f"{visual_type} fits the classified intent {vocabulary['primary_intent']}.",
            "Keep this visual family if the binding remains meaningful.",
            page_id=page_id,
            visual_id=visual.get("id"),
            visual_type=visual_type,
        )
    return build_finding(
        "visual type fit",
        "warning",
        3.0,
        f"{visual_type} is not a primary match for intent {vocabulary['primary_intent']}.",
        f"Consider one of: {', '.join(recommended[:3])}.",
        page_id=page_id,
        visual_id=visual.get("id"),
        visual_type=visual_type,
    )


def _title_finding(
    visual: dict[str, Any],
    *,
    page_id: str,
    binding_count: int,
) -> dict[str, Any]:
    title = visual.get("title")
    visual_type = visual.get("visualType", "unknown")
    if title:
        return build_finding(
            "title clarity",
            "info",
            4.0,
            f"Visual title is '{title}'.",
            "Keep titles specific and outcome-oriented.",
            page_id=page_id,
            visual_id=visual.get("id"),
            visual_type=visual_type,
        )

    severity = "warning" if binding_count > 0 else "info"
    score = 2.4 if binding_count > 0 else 3.2
    return build_finding(
        "title clarity",
        severity,
        score,
        "Visual has no discoverable title.",
        "Add a concise title that explains the metric, segment, or decision context.",
        page_id=page_id,
        visual_id=visual.get("id"),
        visual_type=visual_type,
    )


def visual_design_audit(
    project_path: str,
    page_id: str,
    visual_id: str,
    audience: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    visual = report_get_visual(project_path, page_id, visual_id)
    if "error" in visual:
        return visual

    visual_summary = {
        "id": visual_id,
        "visualType": visual.get("visual", {}).get("visualType", "unknown"),
        "title": None,
    }
    visuals = report_list_visuals(project_path, page_id)
    if "error" not in visuals:
        for item in visuals["visuals"]:
            if item["id"] == visual_id:
                visual_summary = item
                break

    bindings = report_get_visual_bindings(project_path, page_id, visual_id)
    binding_count = int(bindings.get("count", 0)) if "error" not in bindings else 0
    vocabulary = visual_vocabulary_classify(intent or "", audience=audience)
    findings = [
        _title_finding(visual_summary, page_id=page_id, binding_count=binding_count),
        _visual_type_finding(visual_summary, vocabulary, page_id=page_id),
    ]
    score_summary = summarize_scores(findings)

    return {
        "project_path": project_path,
        "page_id": page_id,
        "visual_id": visual_id,
        "visual_type": visual_summary["visualType"],
        "audience": audience,
        "intent": intent,
        "classified_intent": vocabulary,
        "binding_count": binding_count,
        "findings": findings,
        **score_summary,
    }


def page_design_audit(
    project_path: str,
    page_id: str,
    audience: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    pages = report_list_pages(project_path)
    if "error" in pages:
        return pages

    page = next((item for item in pages["pages"] if item["id"] == page_id), None)
    if page is None:
        return {"error": f"Page not found: {page_id}"}

    visuals = report_list_visuals(project_path, page_id)
    if "error" in visuals:
        return visuals

    vocabulary = visual_vocabulary_classify(intent or "", audience=audience)
    findings = [_page_density_finding(page)]
    visual_audits = []
    for visual in visuals["visuals"][:8]:
        audit = visual_design_audit(project_path, page_id, visual["id"], audience, intent)
        if "error" not in audit:
            visual_audits.append(audit)
            findings.extend(audit["findings"])

    score_summary = summarize_scores(findings)
    return {
        "project_path": project_path,
        "page_id": page_id,
        "page_name": page.get("displayName", ""),
        "audience": audience,
        "intent": intent,
        "classified_intent": vocabulary,
        "visual_count": visuals["count"],
        "visual_audits": visual_audits,
        "findings": findings,
        **score_summary,
    }


def _visual_evidence_gate(visual_qa_report_file: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = report_design_desktop_evidence_summary(visual_qa_report_file)
    status = str(summary.get("status") or "unknown")
    totals = summary.get("totals") or {}
    ready_pages = int(totals.get("ready", 0))
    total_pages = int(totals.get("pages", 0))
    allowed = status == "ready"
    gate = {
        "visual_qa_report_file": visual_qa_report_file,
        "desktop_evidence_status": status,
        "screenshot_based_critique_allowed": allowed,
        "ready_pages": ready_pages,
        "total_pages": total_pages,
        "unusable_pages": int(summary.get("unusable_page_count", 0) or 0),
        "recommendation": summary.get("recommendation"),
    }
    if allowed:
        return gate, []

    evidence = f"Desktop evidence status is {status}; {ready_pages}/{total_pages} pages are ready."
    if summary.get("error"):
        evidence = f"{evidence} {summary['error']}"
    finding = build_finding(
        "visual evidence quality",
        "warning",
        3.0,
        evidence,
        "Do not use screenshot-based visual critique until Desktop evidence is ready; continue file-first critique only.",
    )
    return gate, [finding]


def report_design_audit(
    project_path: str,
    audience: str | None = None,
    intent: str | None = None,
    visual_qa_report_file: str | None = None,
) -> dict[str, Any]:
    pages = report_list_pages(project_path)
    if "error" in pages:
        return pages

    page_audits = []
    findings = []
    visual_count = 0
    for page in pages["pages"]:
        visual_count += int(page.get("visual_count", 0))
        audit = page_design_audit(project_path, page["id"], audience, intent)
        if "error" not in audit:
            page_audits.append(audit)
            findings.extend(audit["findings"])

    score_summary = summarize_scores(findings)
    result = {
        "project_path": project_path,
        "audience": audience,
        "intent": intent,
        "page_count": pages["count"],
        "visual_count": visual_count,
        "page_audits": page_audits,
        "findings": findings,
        **score_summary,
    }
    if visual_qa_report_file:
        gate, evidence_findings = _visual_evidence_gate(visual_qa_report_file)
        result["visual_evidence_gate"] = gate
        result["evidence_findings"] = evidence_findings
    return result

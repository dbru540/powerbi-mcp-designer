from typing import Any


VALID_SEVERITIES = {"info", "warning", "error", "critical"}


def grade_for_score(score: float) -> str:
    if score >= 4.5:
        return "excellent"
    if score >= 3.8:
        return "strong"
    if score >= 2.5:
        return "needs-improvement"
    return "weak"


def build_finding(
    dimension: str,
    severity: str,
    score: float,
    evidence: str,
    recommendation: str,
    *,
    page_id: str | None = None,
    page_name: str | None = None,
    visual_id: str | None = None,
    visual_type: str | None = None,
) -> dict[str, Any]:
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"Unsupported severity: {severity}")

    return {
        "dimension": dimension,
        "severity": severity,
        "score": max(0.0, min(5.0, float(score))),
        "evidence": evidence,
        "recommendation": recommendation,
        "page_id": page_id,
        "page_name": page_name,
        "visual_id": visual_id,
        "visual_type": visual_type,
    }


def summarize_scores(findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not findings:
        score = 5.0
    else:
        score = round(sum(float(finding["score"]) for finding in findings) / len(findings), 2)

    return {
        "score": score,
        "grade": grade_for_score(score),
        "finding_count": len(findings),
    }

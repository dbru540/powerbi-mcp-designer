from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    path: str
    pointer: str | None


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue]

    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "issues": [asdict(issue) for issue in self.issues]}

    @staticmethod
    def merge(reports: list[ValidationReport]) -> ValidationReport:
        all_issues: list[ValidationIssue] = []
        for report in reports:
            all_issues.extend(report.issues)
        has_errors = any(issue.severity == "error" for issue in all_issues)
        return ValidationReport(ok=not has_errors, issues=all_issues)

    @staticmethod
    def ok_report() -> ValidationReport:
        return ValidationReport(ok=True, issues=[])

import unittest

from powerbi_mcp.validation.report import ValidationIssue, ValidationReport


class ValidationIssueTests(unittest.TestCase):
    def test_issue_is_frozen_dataclass(self) -> None:
        issue = ValidationIssue(
            severity="error",
            code="TEST_CODE",
            message="Something went wrong",
            path="/some/file.json",
            pointer="/visual/query",
        )
        self.assertEqual(issue.severity, "error")
        self.assertEqual(issue.code, "TEST_CODE")
        with self.assertRaises(AttributeError):
            issue.severity = "warning"  # type: ignore[misc]

    def test_issue_pointer_can_be_none(self) -> None:
        issue = ValidationIssue(
            severity="warning", code="W001", message="Minor",
            path="/some/file.tmdl", pointer=None,
        )
        self.assertIsNone(issue.pointer)


class ValidationReportTests(unittest.TestCase):
    def test_empty_report_is_ok(self) -> None:
        report = ValidationReport(ok=True, issues=[])
        self.assertTrue(report.ok)
        self.assertFalse(report.has_errors())
        self.assertEqual(report.errors(), [])
        self.assertEqual(report.warnings(), [])

    def test_report_with_error_is_not_ok(self) -> None:
        error = ValidationIssue("error", "E001", "Bad", "/f", None)
        report = ValidationReport(ok=False, issues=[error])
        self.assertFalse(report.ok)
        self.assertTrue(report.has_errors())
        self.assertEqual(len(report.errors()), 1)

    def test_report_with_only_warnings_is_ok(self) -> None:
        warning = ValidationIssue("warning", "W001", "Hmm", "/f", None)
        report = ValidationReport(ok=True, issues=[warning])
        self.assertTrue(report.ok)
        self.assertFalse(report.has_errors())
        self.assertEqual(len(report.warnings()), 1)

    def test_merge_combines_issues_and_recomputes_ok(self) -> None:
        r1 = ValidationReport(ok=True, issues=[
            ValidationIssue("warning", "W001", "w", "/a", None),
        ])
        r2 = ValidationReport(ok=False, issues=[
            ValidationIssue("error", "E001", "e", "/b", None),
        ])
        merged = ValidationReport.merge([r1, r2])
        self.assertFalse(merged.ok)
        self.assertEqual(len(merged.issues), 2)

    def test_merge_empty_list_returns_ok(self) -> None:
        merged = ValidationReport.merge([])
        self.assertTrue(merged.ok)
        self.assertEqual(merged.issues, [])

    def test_to_dict_serializes_correctly(self) -> None:
        issue = ValidationIssue("error", "E001", "Bad thing", "/f.json", "/a/b")
        report = ValidationReport(ok=False, issues=[issue])
        d = report.to_dict()
        self.assertFalse(d["ok"])
        self.assertEqual(len(d["issues"]), 1)
        self.assertEqual(d["issues"][0]["code"], "E001")
        self.assertEqual(d["issues"][0]["pointer"], "/a/b")


if __name__ == "__main__":
    unittest.main()

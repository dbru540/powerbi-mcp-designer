import json
import unittest
from pathlib import Path

from powerbi_mcp.tests._temp_roots import named_temp_root
from powerbi_mcp.visual_ai.qa_loop import (
    compare_screenshot_to_baseline,
    discover_pbip_projects,
    run_file_first_visual_qa_loop,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PARENT = REPO_ROOT
FIXTURE_PROJECT_PATH = REPO_ROOT / "example"
TEMP_ROOT = named_temp_root("visual_ai_qa_loop")


class VisualAIQALoopTests(unittest.TestCase):
    def tearDown(self) -> None:
        if TEMP_ROOT.exists():
            for child in TEMP_ROOT.iterdir():
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    import shutil

                    shutil.rmtree(child, ignore_errors=True)
            try:
                TEMP_ROOT.rmdir()
            except OSError:
                pass

    def test_discover_pbip_projects_finds_fixture_project(self) -> None:
        projects = discover_pbip_projects(str(FIXTURE_PARENT))

        matching = [project for project in projects if project["project_path"] == str(FIXTURE_PROJECT_PATH)]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["name"], "Focus")
        self.assertEqual(matching[0]["pbip_file"], str(FIXTURE_PROJECT_PATH / "Focus.pbip"))

    def test_file_first_visual_qa_loop_writes_mvp_ready_report_without_desktop(self) -> None:
        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            output_dir=str(TEMP_ROOT),
            page_limit=1,
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["project_count"], 1)
        self.assertFalse(result["desktop"]["launch_requested"])
        self.assertTrue(result["report_file"].endswith("visual-qa-report.json"))
        self.assertTrue(Path(result["report_file"]).exists())
        self.assertEqual(result["projects"][0]["readiness"]["status"], "mvp-ready")
        self.assertEqual(result["projects"][0]["status"], "passed")

        written = json.loads(Path(result["report_file"]).read_text(encoding="utf-8"))
        self.assertEqual(written["status"], "passed")
        self.assertEqual(written["projects"][0]["project_path"], str(FIXTURE_PROJECT_PATH))

    def test_desktop_launch_requires_existing_executable(self) -> None:
        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            pbidesktop_path=str(TEMP_ROOT / "missing" / "PBIDesktop.exe"),
            launch_desktop=True,
            output_dir=str(TEMP_ROOT),
            page_limit=1,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["desktop"]["launch_requested"])
        self.assertFalse(result["desktop"]["path_ok"])
        self.assertIn("not found", result["desktop"]["error"])

    def test_desktop_screenshot_backend_records_capture_artifact_after_launch(self) -> None:
        fake_desktop = TEMP_ROOT / "PBIDesktop.exe"
        fake_desktop.parent.mkdir(parents=True, exist_ok=True)
        fake_desktop.write_text("", encoding="utf-8")

        def fake_launcher(pbidesktop_path: str, pbip_file: str) -> dict:
            return {
                "attempted": True,
                "pid": 1234,
                "screenshot": {
                    "attempted": False,
                    "path": None,
                    "window_title": None,
                    "error": None,
                },
                "visual_comparison": {"attempted": False, "status": "not-requested"},
                "error": None,
            }

        def fake_screenshot_backend(
            pid: int | None,
            project: dict,
            output_dir: Path,
            wait_seconds: float,
        ) -> dict:
            screenshot_path = output_dir / f"{project['name']}-desktop.bmp"
            screenshot_path.write_bytes(b"fake screenshot")
            return {
                "attempted": True,
                "path": str(screenshot_path),
                "window_title": "Power BI Desktop - Focus",
                "error": None,
            }

        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            pbidesktop_path=str(fake_desktop),
            launch_desktop=True,
            capture_screenshot=True,
            output_dir=str(TEMP_ROOT),
            page_limit=1,
            desktop_launcher=fake_launcher,
            screenshot_backend=fake_screenshot_backend,
        )

        project = result["projects"][0]
        screenshot = project["desktop_launch"]["screenshot"]
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["desktop"]["launch_attempted"])
        self.assertEqual(result["desktop"]["pids"], [1234])
        self.assertTrue(screenshot["attempted"])
        self.assertTrue(Path(screenshot["path"]).exists())
        self.assertEqual(screenshot["window_title"], "Power BI Desktop - Focus")

    def test_capture_all_pages_records_one_screenshot_per_report_page(self) -> None:
        fake_desktop = TEMP_ROOT / "PBIDesktop.exe"
        fake_desktop.parent.mkdir(parents=True, exist_ok=True)
        fake_desktop.write_text("", encoding="utf-8")
        navigation_calls = []

        def fake_launcher(pbidesktop_path: str, pbip_file: str) -> dict:
            return {
                "attempted": True,
                "pid": 1234,
                "screenshot": {
                    "attempted": False,
                    "path": None,
                    "window_title": None,
                    "error": None,
                },
                "page_screenshots": [],
                "visual_comparison": {"attempted": False, "status": "not-requested"},
                "error": None,
            }

        def fake_screenshot_backend(
            pid: int | None,
            project: dict,
            output_dir: Path,
            wait_seconds: float,
        ) -> dict:
            screenshot_path = output_dir / f"{project['capture_name']}.bmp"
            screenshot_path.write_bytes(project["active_page"]["id"].encode("utf-8"))
            return {
                "attempted": True,
                "path": str(screenshot_path),
                "window_title": f"Power BI Desktop - {project['active_page']['displayName']}",
                "error": None,
            }

        def fake_page_navigator(
            pid: int | None,
            project: dict,
            page: dict,
            page_index: int,
            delay_seconds: float,
        ) -> dict:
            navigation_calls.append((page_index, page["id"]))
            return {"attempted": True, "page_index": page_index, "page_id": page["id"], "error": None}

        def fake_readiness_analyzer(screenshot_path: str | None) -> dict:
            return {
                "attempted": True,
                "status": "ready",
                "path": screenshot_path,
                "content_ratio": 0.42,
                "error": None,
            }

        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            pbidesktop_path=str(fake_desktop),
            launch_desktop=True,
            capture_screenshot=True,
            capture_all_pages=True,
            screenshot_page_limit=2,
            output_dir=str(TEMP_ROOT),
            page_limit=1,
            desktop_launcher=fake_launcher,
            screenshot_backend=fake_screenshot_backend,
            page_navigator=fake_page_navigator,
            screenshot_readiness_analyzer=fake_readiness_analyzer,
        )

        page_screenshots = result["projects"][0]["desktop_launch"]["page_screenshots"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(page_screenshots), 2)
        self.assertEqual(len(navigation_calls), 2)
        self.assertEqual(page_screenshots[0]["page_index"], 0)
        self.assertEqual(page_screenshots[1]["page_index"], 1)
        self.assertTrue(Path(page_screenshots[0]["screenshot"]["path"]).exists())
        self.assertTrue(Path(page_screenshots[1]["screenshot"]["path"]).exists())
        self.assertEqual(page_screenshots[0]["render_readiness"]["status"], "ready")
        self.assertEqual(page_screenshots[1]["render_readiness"]["content_ratio"], 0.42)
        self.assertEqual(result["projects"][0]["desktop_launch"]["screenshot"], page_screenshots[0]["screenshot"])

    def test_capture_retries_until_render_readiness_is_ready(self) -> None:
        fake_desktop = TEMP_ROOT / "PBIDesktop.exe"
        fake_desktop.parent.mkdir(parents=True, exist_ok=True)
        fake_desktop.write_text("", encoding="utf-8")
        screenshot_calls = []

        def fake_launcher(pbidesktop_path: str, pbip_file: str) -> dict:
            return {
                "attempted": True,
                "pid": 1234,
                "screenshot": {"attempted": False, "path": None, "window_title": None, "error": None},
                "page_screenshots": [],
                "visual_comparison": {"attempted": False, "status": "not-requested"},
                "error": None,
            }

        def fake_screenshot_backend(pid: int | None, project: dict, output_dir: Path, wait_seconds: float) -> dict:
            attempt = len(screenshot_calls) + 1
            screenshot_calls.append(attempt)
            screenshot_path = output_dir / f"{project['capture_name']}-{attempt}.bmp"
            screenshot_path.write_bytes(f"attempt {attempt}".encode("utf-8"))
            return {"attempted": True, "path": str(screenshot_path), "window_title": "Power BI", "error": None}

        def fake_readiness_analyzer(screenshot_path: str | None) -> dict:
            status = "ready" if len(screenshot_calls) == 2 else "low-content"
            return {"attempted": True, "path": screenshot_path, "status": status, "error": None}

        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            pbidesktop_path=str(fake_desktop),
            launch_desktop=True,
            capture_screenshot=True,
            capture_all_pages=True,
            screenshot_page_limit=1,
            render_readiness_retry_seconds=30,
            render_readiness_retry_interval_seconds=1,
            output_dir=str(TEMP_ROOT),
            page_limit=1,
            desktop_launcher=fake_launcher,
            screenshot_backend=fake_screenshot_backend,
            page_navigator=lambda pid, project, page, page_index, delay: {"attempted": True, "error": None},
            screenshot_readiness_analyzer=fake_readiness_analyzer,
            sleeper=lambda seconds: None,
        )

        page_capture = result["projects"][0]["desktop_launch"]["page_screenshots"][0]
        evidence_studio = result["projects"][0]["visual_evidence_studio"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["desktop_evidence_summary"]["status"], "ready")
        self.assertEqual(result["desktop_evidence_summary"]["totals"]["ready"], 1)
        self.assertEqual(len(screenshot_calls), 2)
        self.assertEqual(len(page_capture["render_attempts"]), 2)
        self.assertEqual(page_capture["render_readiness"]["status"], "ready")
        self.assertTrue(page_capture["screenshot"]["path"].endswith("-2.bmp"))
        self.assertEqual(evidence_studio["critique_mode"], "screenshot-informed")
        self.assertTrue(evidence_studio["visual_evidence_gate"]["screenshot_based_critique_allowed"])

    def test_capture_retry_timeout_keeps_last_low_content_attempt(self) -> None:
        fake_desktop = TEMP_ROOT / "PBIDesktop.exe"
        fake_desktop.parent.mkdir(parents=True, exist_ok=True)
        fake_desktop.write_text("", encoding="utf-8")
        now = {"seconds": 0.0}
        screenshot_calls = []

        def fake_launcher(pbidesktop_path: str, pbip_file: str) -> dict:
            return {
                "attempted": True,
                "pid": 1234,
                "screenshot": {"attempted": False, "path": None, "window_title": None, "error": None},
                "page_screenshots": [],
                "visual_comparison": {"attempted": False, "status": "not-requested"},
                "error": None,
            }

        def fake_screenshot_backend(pid: int | None, project: dict, output_dir: Path, wait_seconds: float) -> dict:
            attempt = len(screenshot_calls) + 1
            screenshot_calls.append(attempt)
            screenshot_path = output_dir / f"{project['capture_name']}-{attempt}.bmp"
            screenshot_path.write_bytes(f"attempt {attempt}".encode("utf-8"))
            return {"attempted": True, "path": str(screenshot_path), "window_title": "Power BI", "error": None}

        def fake_sleep(seconds: float) -> None:
            now["seconds"] += seconds

        result = run_file_first_visual_qa_loop(
            str(FIXTURE_PARENT),
            audience="executive",
            intent="overview of consulting performance",
            pbidesktop_path=str(fake_desktop),
            launch_desktop=True,
            capture_screenshot=True,
            capture_all_pages=True,
            screenshot_page_limit=1,
            render_readiness_retry_seconds=2,
            render_readiness_retry_interval_seconds=1,
            output_dir=str(TEMP_ROOT),
            page_limit=1,
            desktop_launcher=fake_launcher,
            screenshot_backend=fake_screenshot_backend,
            page_navigator=lambda pid, project, page, page_index, delay: {"attempted": True, "error": None},
            screenshot_readiness_analyzer=lambda screenshot_path: {
                "attempted": True,
                "path": screenshot_path,
                "status": "low-content",
                "error": "blank",
            },
            clock=lambda: now["seconds"],
            sleeper=fake_sleep,
        )

        page_capture = result["projects"][0]["desktop_launch"]["page_screenshots"][0]
        evidence_studio = result["projects"][0]["visual_evidence_studio"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(page_capture["render_attempts"]), 3)
        self.assertEqual(page_capture["render_readiness"]["status"], "low-content")
        self.assertEqual(page_capture["render_retry"]["status"], "timeout")
        self.assertEqual(evidence_studio["critique_mode"], "file-first-only")
        self.assertFalse(evidence_studio["visual_evidence_gate"]["screenshot_based_critique_allowed"])

    def test_screenshot_baseline_comparison_reports_match_and_missing_baseline(self) -> None:
        actual = TEMP_ROOT / "actual.bmp"
        baseline_dir = TEMP_ROOT / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        actual.write_bytes(b"same screenshot bytes")
        baseline = baseline_dir / actual.name
        baseline.write_bytes(b"same screenshot bytes")

        matched = compare_screenshot_to_baseline(str(actual), str(baseline_dir))
        self.assertTrue(matched["attempted"])
        self.assertEqual(matched["status"], "matched")
        self.assertEqual(matched["actual_sha256"], matched["baseline_sha256"])

        baseline.unlink()
        missing = compare_screenshot_to_baseline(str(actual), str(baseline_dir))
        self.assertEqual(missing["status"], "missing-baseline")
        self.assertIsNone(missing["baseline_sha256"])


if __name__ == "__main__":
    unittest.main()

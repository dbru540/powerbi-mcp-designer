from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from powerbi_mcp.visual_ai.qa_loop import run_file_first_visual_qa_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repeated file-first Power BI report-design QA over PBIP test projects."
    )
    parser.add_argument("--test-root", required=True, help="Directory containing one or more PBIP projects.")
    parser.add_argument("--audience", default="executive", help="Target report audience.")
    parser.add_argument("--intent", default="overview of report performance", help="Design intent to evaluate.")
    parser.add_argument("--subject", default=None, help="Optional report subject/domain.")
    parser.add_argument("--page-limit", type=int, default=1, help="Number of pages per report to include.")
    parser.add_argument(
        "--pbidesktop-path",
        default=None,
        help="Optional path to PBIDesktop.exe for interactive launch probes.",
    )
    parser.add_argument(
        "--launch-desktop",
        action="store_true",
        help="Launch Power BI Desktop for each discovered PBIP after file-first checks.",
    )
    parser.add_argument(
        "--capture-screenshot",
        action="store_true",
        help="After launching Desktop, wait for a visible Power BI window and capture it as BMP.",
    )
    parser.add_argument(
        "--capture-all-pages",
        action="store_true",
        help="Capture one screenshot per report page, navigating visible Desktop between captures.",
    )
    parser.add_argument(
        "--desktop-wait-seconds",
        type=float,
        default=45,
        help="Seconds to wait for a visible Power BI Desktop window before screenshot capture fails.",
    )
    parser.add_argument(
        "--screenshot-page-limit",
        type=int,
        default=None,
        help="Maximum number of report pages to capture when --capture-all-pages is used.",
    )
    parser.add_argument(
        "--page-navigation-delay-seconds",
        type=float,
        default=2,
        help="Seconds to wait after Desktop page navigation before capturing the next page.",
    )
    parser.add_argument(
        "--render-readiness-retry-seconds",
        type=float,
        default=0,
        help="Seconds to keep recapturing when the report canvas appears blank or still loading.",
    )
    parser.add_argument(
        "--render-readiness-retry-interval-seconds",
        type=float,
        default=5,
        help="Seconds to wait between render-readiness retry captures.",
    )
    parser.add_argument(
        "--baseline-dir",
        default=None,
        help="Optional directory containing baseline screenshots with matching filenames for SHA-256 comparison.",
    )
    parser.add_argument(
        "--output-dir",
        default="C:/_pbimcp_visual_qa",
        help="Directory where visual-qa-report.json will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_file_first_visual_qa_loop(
        test_root=args.test_root,
        audience=args.audience,
        intent=args.intent,
        subject=args.subject,
        pbidesktop_path=args.pbidesktop_path,
        launch_desktop=args.launch_desktop,
        capture_screenshot=args.capture_screenshot,
        capture_all_pages=args.capture_all_pages,
        desktop_wait_seconds=args.desktop_wait_seconds,
        screenshot_page_limit=args.screenshot_page_limit,
        page_navigation_delay_seconds=args.page_navigation_delay_seconds,
        render_readiness_retry_seconds=args.render_readiness_retry_seconds,
        render_readiness_retry_interval_seconds=args.render_readiness_retry_interval_seconds,
        baseline_dir=args.baseline_dir,
        output_dir=args.output_dir,
        page_limit=args.page_limit,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

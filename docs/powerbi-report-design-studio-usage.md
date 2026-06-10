# Power BI Report Design Studio Usage

This server is now usable as a file-first Power BI report design assistant for PBIP/PBIR projects.

It does not replace Power BI Desktop. It reads and edits local PBIR/TMDL files, validates changes, and keeps risky design operations dry-run by default.

## Recommended Entry Point

Start with:

```text
report_design_readiness_check
```

Use it with:

```json
{
  "project_path": "C:/path/to/project",
  "audience": "executive",
  "intent": "overview of consulting margin performance",
  "page_limit": 1
}
```

Expected status for a valid local project:

```text
mvp-ready
```

This means the server can safely support AI-assisted report critique, design planning, title quick wins, grid alignment, and reviewed reflow plans. It does not mean fully automated production report design is safe without visual review.

## Core Workflow

1. Run `report_design_readiness_check`.
2. Run `report_design_studio_plan` to get a complete read-only design plan.
3. Inspect page studies, action counts, and remaining gates.
4. Run apply tools in dry-run mode first:
   - `page_design_apply_quick_wins`
   - `page_layout_apply_quick_wins`
   - `page_layout_apply_reflow_plan`
5. If dry-run output is acceptable, apply a small page-scoped write.
6. Open in Power BI Desktop or another visual review surface before broad application.

## Main Design Tools

Read-only tools:

- `report_design_audit`: scores report/page/visual design quality.
- `report_design_visual_qa_loop`: runs repeated file-first QA over PBIP folders and can optionally launch Desktop for screenshot capture.
- `report_design_desktop_evidence_summary`: summarizes an existing `visual-qa-report.json` to identify which Desktop screenshots are usable before visual critique.
- `page_layout_analyze`: detects zones, overlaps, focal candidates, and visual density.
- `page_layout_blueprint_generate`: proposes an audience-specific layout blueprint.
- `page_layout_recommend`: compares a page to the blueprint.
- `page_layout_reflow_plan`: maps existing visuals into blueprint zones.
- `report_design_studio_plan`: orchestrates audit, layout, quick wins, and reflow plans.
- `report_design_readiness_check`: reports whether the current server/project pair is MVP-ready.

Write-capable tools, dry-run by default where design risk is higher:

- `page_design_apply_quick_wins`: adds missing titles to bound visuals.
- `page_layout_apply_quick_wins`: snaps data visuals to a grid.
- `page_layout_apply_reflow_plan`: moves existing visuals toward an audience blueprint.
- `visual_plan_generate_and_apply`: generates and applies supported native visual families.

## Current Safety Boundary

Supported:

- Local PBIP/PBIR/TMDL file-first work.
- Built-in native visual generation for supported visual families.
- Validated report writes with backups.
- Read-only design critique and studio orchestration.
- Dry-run-first design actions.
- Optional Power BI Desktop screenshot evidence, including one screenshot per report page.

Supported native generation families currently include:

- Data visuals: `card`, `lineChart`, `barChart`, `columnChart`, `clusteredBarChart`, `clusteredColumnChart`, `pieChart`, `donutChart`, `tableEx`, `pivotTable`, and `slicer`.
- Presentation visuals: `textbox`, `shape`, and `image`.

`create_visual` also accepts optional `role_assignments` for PBIR-native role names, for example `Values` for `card`, `slicer`, and `tableEx`, or `Rows` / `Columns` / `Values` for `pivotTable`. The legacy `category_entity` / `category_property` and `measure_entity` / `measure_property` parameters remain available for simple chart creation.

Not yet production-automated:

- Perceptual/pixel-tolerance visual comparison. Current screenshot comparison is exact SHA-256 baseline matching.
- Computer-vision detection that a Desktop page has fully rendered. Use a conservative page navigation delay for PBIP files with slow queries.
- Full-page automatic reflow without human review.
- Deneb/custom visual generation.
- Live Fabric/Desktop semantic model operations. Those should coexist with `microsoft/powerbi-modeling-mcp`.

## Practical Agent Prompt

Use this prompt shape with an MCP-capable agent:

```text
Use report_design_readiness_check on this PBIP project.
If status is mvp-ready, call report_design_studio_plan for an executive audience.
Then propose a dry-run-only execution sequence.
Do not apply writes until dry-run actions are reviewed.
```

This keeps the agent in the safe lane: critique first, dry-run second, reviewed apply last.

## Repeated Visual QA Loop

For a local test folder containing one or more `.pbip` files:

```powershell
.\mcp\venv\Scripts\python.exe scripts\powerbi_visual_qa_loop.py `
  --test-root "C:\path\to\pbip-test-folder" `
  --pbidesktop-path "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe" `
  --audience executive `
  --intent "overview of questionnaire satisfaction" `
  --page-limit 1 `
  --output-dir "C:\_pbimcp_visual_qa\questionnaires"
```

To launch Power BI Desktop and capture a visible Desktop window as a BMP artifact, add:

```powershell
  --launch-desktop --capture-screenshot --desktop-wait-seconds 90
```

To capture one Desktop screenshot per report page, add:

```powershell
  --launch-desktop `
  --capture-screenshot `
  --capture-all-pages `
  --screenshot-page-limit 3 `
  --desktop-wait-seconds 90 `
  --page-navigation-delay-seconds 15 `
  --render-readiness-retry-seconds 60 `
  --render-readiness-retry-interval-seconds 10
```

`--desktop-wait-seconds` waits for a visible Power BI Desktop window. `--page-navigation-delay-seconds` waits after page focus/navigation before each page capture. Slow PBIP files may need a larger page delay because Desktop can show a visible window before visuals and queries have finished rendering.

If `--baseline-dir` is provided, the captured screenshot is compared by exact SHA-256 hash against a file of the same name in that directory. This is intentionally strict and should be treated as a first gate before a future perceptual visual-diff engine.

Each captured screenshot also receives a non-blocking `render_readiness` verdict:

- `ready`: the central report canvas has enough non-white content or contrast to be useful as visual evidence.
- `low-content`: the screenshot was captured, but the report canvas appears blank or still loading.
- `missing-actual` / `unsupported`: the screenshot could not be analyzed.

This verdict is not a design score. It is a guardrail that prevents the AI from trusting a screenshot that contains only Desktop chrome, a loading state, or an empty canvas.

When `--render-readiness-retry-seconds` is greater than zero, the QA loop recaptures the same page until `render_readiness.status` becomes `ready` or the timeout expires. The report keeps every attempt in `render_attempts` and records retry metadata in `render_retry`. A timeout is evidence-quality information; it does not fail the file-first QA result unless Desktop capture itself errors.

When screenshots are requested, the QA report also adds `projects[].visual_evidence_studio` after the report file is written. This is a post-capture `report_design_studio_plan` result using the generated `visual-qa-report.json` as `visual_qa_report_file`, so agents can read `critique_mode` directly:

- `screenshot-informed`: captured Desktop evidence is ready and can be used for visual critique.
- `file-first-only`: screenshots are blank, missing, unsupported, or still rendering; use PBIR metadata critique only.

The QA report also includes a top-level `desktop_evidence_summary` so agents can quickly decide whether screenshot-based critique is safe. To summarize an existing report through MCP, call:

```text
report_design_desktop_evidence_summary
```

with:

```json
{
  "report_file": "C:/_pbimcp_visual_qa/questionnaires-render-retry/visual-qa-report.json"
}
```

Use pages with `evidence_status: "ready"` for visual critique. Treat `low-content`, `missing-actual`, and `unsupported` as evidence gaps, not design failures.

`report_design_audit` can also receive `visual_qa_report_file`. When provided, it adds:

- `visual_evidence_gate`: whether screenshot-based critique is allowed for the supplied Desktop evidence.
- `evidence_findings`: non-scoring evidence warnings such as low-content screenshots or missing captures.

This does not change the report design `score`; it only prevents agents from treating blank screenshots as visual truth.

`report_design_studio_plan` accepts the same `visual_qa_report_file` parameter. When supplied, the studio plan adds:

- `critique_mode: "screenshot-informed"` when Desktop evidence is ready.
- `critique_mode: "file-first-only"` when screenshots are low-content, missing, unsupported, or still rendering.
- `critique_guidance`, `visual_evidence_gate`, and `evidence_findings` so agents know whether to use screenshot evidence or stay on PBIR metadata critique.

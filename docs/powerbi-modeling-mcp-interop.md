# Power BI Modeling MCP Interop

This repository is intended to complement, not replace, `microsoft/powerbi-modeling-mcp`.

## Recommended Split

### This repo owns

- PBIP/PBIR file-first report and UI metadata operations
- local TMDL reads and local TMDL file writes inside a PBIP workspace
- report-to-model binding analysis and report impact helpers

### `microsoft/powerbi-modeling-mcp` owns

- live semantic-model operations against Power BI Desktop
- live semantic-model operations against Fabric workspaces
- broader modeling workflows beyond local PBIP file mutation

## Do Not Duplicate

- Desktop/Fabric connection handling
- live model session orchestration
- the broad live-model authoring surface already owned by Microsoft's server

## Recommended Combined Workflow

1. Use this repo to edit PBIP report/UI artifacts and local PBIP/TMDL files.
2. Use Microsoft's server when the task requires a live semantic model in Desktop or Fabric.
3. Use this repo's binding and impact tools before renaming or deleting semantic-model objects that feed report visuals.

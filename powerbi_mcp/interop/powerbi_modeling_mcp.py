def get_powerbi_modeling_mcp_interop_guidance() -> dict:
    return {
        "recommended_split": {
            "this_repo": [
                "PBIP/PBIR file-first report and UI metadata operations",
                "Local TMDL reads and local TMDL file writes inside a PBIP workspace",
                "Report-to-model binding analysis and report impact helpers",
            ],
            "microsoft_powerbi_modeling_mcp": [
                "Live semantic-model operations against Power BI Desktop",
                "Live semantic-model operations against Fabric workspaces",
                "Broader modeling workflows beyond local PBIP file mutation",
            ],
        },
        "do_not_duplicate": [
            "Desktop/Fabric connection handling",
            "live model session orchestration",
            "broad live-model authoring surface already owned by Microsoft's server",
        ],
        "recommended_workflow": [
            "Use this repo to edit PBIP report/UI artifacts and local file-based model metadata",
            "Use Microsoft's server when the task requires a live semantic model in Desktop or Fabric",
            "Use binding and impact tools here before renaming or deleting model objects that drive report visuals",
        ],
        "interop_status": "complementary",
    }

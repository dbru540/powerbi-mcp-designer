# Install Power BI MCP Server

Power BI MCP Server is designed to run locally through stdio, like many MCP
servers used by Claude Code, Codex, and other MCP-compatible clients.

## Recommended: uvx

After the package is published to PyPI:

```bash
uvx powerbi-mcp-designer
```

Add it to Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx powerbi-mcp-designer
```

Add it to Codex:

```bash
codex mcp add powerbi-mcp -- uvx powerbi-mcp-designer
```

## Persistent Local Install

Use this when you want the command installed once on the machine:

```bash
uv tool install powerbi-mcp-designer
powerbi-mcp-doctor
```

Then configure clients with the installed command:

```bash
claude mcp add --transport stdio powerbi-mcp -- powerbi-mcp-designer
codex mcp add powerbi-mcp -- powerbi-mcp-designer
```

## GitHub Direct Install

Before PyPI publication, or for a private GitHub repository, users can run the
server directly from a tagged Git repository:

```bash
uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.0 powerbi-mcp-designer
```

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.0 powerbi-mcp-designer
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.0 powerbi-mcp-designer
```

## Development Install

From this repository:

```bash
uv pip install -e .
powerbi-mcp-doctor --project ./example --no-validate
```

If `uv` is not available:

```bash
python -m pip install -e .
powerbi-mcp-doctor --project ./example --no-validate
```

## Client Config Files

Claude Code project-scoped example:

```json
{
  "mcpServers": {
    "powerbi-mcp": {
      "command": "uvx",
      "args": ["powerbi-mcp-designer"]
    }
  }
}
```

Codex project-scoped example:

```toml
[mcp_servers.powerbi_mcp]
command = "uvx"
args = ["powerbi-mcp-designer"]
startup_timeout_sec = 20
tool_timeout_sec = 120
```

## Diagnostics

Run:

```bash
powerbi-mcp-doctor
powerbi-mcp-doctor --project "C:/path/to/report.pbip-parent"
```

The doctor checks Python, package dependencies, optional Power BI Desktop
availability, PBIP project structure, and validation errors when a project is
provided.

## Publishing Checklist

Before publishing to PyPI:

1. Create the public or private GitHub repository and add the real project URLs
   to `pyproject.toml`.
2. Create a PyPI project named `powerbi-mcp-designer`.
3. Configure PyPI Trusted Publishing for the GitHub Actions workflow.
4. Run CI and publish to TestPyPI first.
5. Tag a release and publish to PyPI.

See [RELEASE.md](RELEASE.md) for the operational release process.

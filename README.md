# Power BI MCP Designer

File-first MCP server for designing Power BI report visuals, pages and layouts (PBIP/PBIR/TMDL).

The canonical Python package is `powerbi_mcp`. It intentionally avoids using
`mcp` as the local package name so imports can coexist with the official Model
Context Protocol Python SDK.

## Quick Start

After publication to PyPI, run it locally with `uvx`:

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

For local development from this repository:

```bash
python -m powerbi_mcp.server
```

Check the local environment:

```bash
powerbi-mcp-doctor --project ./example --no-validate
```

Run the test suite with:

```bash
python -m unittest discover -s powerbi_mcp/tests
```

See [README_INSTALL.md](README_INSTALL.md) for full installation and publishing
instructions.

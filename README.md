# Power BI MCP Server

Local MCP server for file-first Power BI PBIP/PBIR/TMDL automation and report
design assistance.

The canonical Python package is `powerbi_mcp`. It intentionally avoids using
`mcp` as the local package name so imports can coexist with the official Model
Context Protocol Python SDK.

## Quick Start

After publication to PyPI, run it locally with `uvx`:

```bash
uvx powerbi-mcp-server-540
```

Add it to Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx powerbi-mcp-server-540
```

Add it to Codex:

```bash
codex mcp add powerbi-mcp -- uvx powerbi-mcp-server-540
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

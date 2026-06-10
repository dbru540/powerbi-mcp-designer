# Release Process

This project is distributed as a local stdio MCP server through the Python
package `powerbi-mcp-server`.

## One-Time Setup

1. Create the GitHub repository.
2. Add the remote locally:

   ```bash
   git remote add origin https://github.com/<owner>/<repo>.git
   ```

3. Add the real GitHub URLs to `pyproject.toml`:

   ```toml
   [project.urls]
   Homepage = "https://github.com/<owner>/<repo>"
   Repository = "https://github.com/<owner>/<repo>"
   Issues = "https://github.com/<owner>/<repo>/issues"
   ```

4. Create the PyPI project `powerbi-mcp-server`.
5. Configure PyPI Trusted Publishing:

   - Publisher: GitHub
   - Owner: `<owner>`
   - Repository: `<repo>`
   - Workflow: `publish.yml`
   - Environment: `pypi`

6. Configure TestPyPI Trusted Publishing with the same values and environment
   `testpypi`.
7. In GitHub repository settings, create environments named `pypi` and
   `testpypi`.

## Local Release Validation

Use Windows Python for parity with the Power BI Desktop environment:

```bash
python -m unittest discover -s powerbi_mcp/tests
python powerbi_mcp/smoke_test.py
python -m pip install build
python -m build
python scripts/check_distribution.py --dist-dir dist
```

Verify the wheel in a clean environment:

```bash
python -m venv C:/_pbimcp_pkg_install_venv
C:/_pbimcp_pkg_install_venv/Scripts/python.exe -m pip install --upgrade pip
C:/_pbimcp_pkg_install_venv/Scripts/python.exe -m pip install dist/powerbi_mcp_server-0.1.0-py3-none-any.whl
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-server.exe --help
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-doctor.exe --project example --no-validate
```

Verify `uvx` behavior:

```bash
uvx --from dist/powerbi_mcp_server-0.1.0-py3-none-any.whl powerbi-mcp-server --help
```

## Publish to TestPyPI

Run the GitHub Actions workflow manually:

```text
Actions -> Publish Python Package -> Run workflow -> target: testpypi
```

Then verify install:

```bash
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ powerbi-mcp-server --help
```

## Publish to PyPI

Create and publish a GitHub release. The `publish.yml` workflow publishes the
built distributions to PyPI through Trusted Publishing.

Verify public install:

```bash
uvx powerbi-mcp-server --help
powerbi-mcp-doctor
```

## Client Setup After Publication

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx powerbi-mcp-server
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx powerbi-mcp-server
```

## GitHub-Only Distribution

If PyPI is not ready yet, publish a GitHub tag and install directly from Git:

```bash
uvx --from git+https://github.com/<owner>/<repo>.git@v0.1.0 powerbi-mcp-server --help
```

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx --from git+https://github.com/<owner>/<repo>.git@v0.1.0 powerbi-mcp-server
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx --from git+https://github.com/<owner>/<repo>.git@v0.1.0 powerbi-mcp-server
```

## Known Local Blockers

The current local environment does not have `gh` installed and this repository
does not yet have a Git remote. Repository creation, GitHub environment setup,
and PyPI Trusted Publishing must be completed from an authenticated GitHub/PyPI
account.

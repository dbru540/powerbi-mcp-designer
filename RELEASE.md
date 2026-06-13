# Release Process

This project is distributed as a local stdio MCP server through the Python
package `powerbi-mcp-designer`.

## One-Time Setup

1. Create the GitHub repository.
2. Add the remote locally:

   ```bash
   git remote add origin https://github.com/dbru540/powerbi-mcp-designer.git
   ```

3. Add the real GitHub URLs to `pyproject.toml`:

   ```toml
   [project.urls]
   Homepage = "https://github.com/dbru540/powerbi-mcp-designer"
   Repository = "https://github.com/dbru540/powerbi-mcp-designer"
   Issues = "https://github.com/dbru540/powerbi-mcp-designer/issues"
   ```

4. Create the TestPyPI pending publisher for `powerbi-mcp-designer`.
5. Configure TestPyPI Trusted Publishing:

   - Publisher: GitHub
   - Owner: `dbru540`
   - Repository: `powerbi-mcp-designer`
   - Workflow: `publish.yml`
   - Environment: `testpypi`

6. Configure PyPI Trusted Publishing for `powerbi-mcp-designer` with:

   - Publisher: GitHub
   - Owner: `dbru540`
   - Repository: `powerbi-mcp-designer`
   - Workflow: `publish.yml`
   - Environment: `pypi`

7. GitHub repository environments `pypi` and `testpypi` must exist on
   `dbru540/powerbi-mcp-designer` (created during the 0.2.1 rename setup).

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
C:/_pbimcp_pkg_install_venv/Scripts/python.exe -m pip install dist/powerbi_mcp_designer-0.2.1-py3-none-any.whl
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-designer.exe --help
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-doctor.exe --project example --no-validate
```

Verify `uvx` behavior:

```bash
uvx --from dist/powerbi_mcp_designer-0.2.1-py3-none-any.whl powerbi-mcp-designer --help
```

## Publish to TestPyPI

Run the GitHub Actions workflow manually:

```text
Actions -> Publish Python Package -> Run workflow -> target: testpypi
```

Then verify install:

```bash
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ powerbi-mcp-designer --help
```

## Publish to PyPI

Create and publish a GitHub release. The `publish.yml` workflow publishes the
built distributions to PyPI through Trusted Publishing.

Verify public install:

```bash
uvx powerbi-mcp-designer --help
powerbi-mcp-doctor
```

## Client Setup After Publication

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx powerbi-mcp-designer
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx powerbi-mcp-designer
```

## GitHub-Only Distribution

If PyPI is not ready yet, publish a GitHub tag and install directly from Git:

```bash
uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.1 powerbi-mcp-designer --help
```

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.1 powerbi-mcp-designer
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-designer.git@v0.2.1 powerbi-mcp-designer
```

## Published Release State

Version `0.2.1` (`powerbi-mcp-designer`) is **pending publication** — not
yet released. This is a rename of the project; before publishing, redo the
One-Time Setup above for the new PyPI project name (a new Trusted Publisher must
be created on both PyPI and TestPyPI for `powerbi-mcp-designer`).

After publishing, verify the public install:

```bash
uvx powerbi-mcp-designer --help
powerbi-mcp-doctor
```

### Previous release (legacy name)

Version `0.1.2` was published under the former package name
`powerbi-mcp-server-540`:

- TestPyPI workflow run: `27301193950`
- PyPI workflow run: `27301286835`
- GitHub tag: `v0.1.2`
- PyPI URL: `https://pypi.org/project/powerbi-mcp-server-540/`

# Release Process

This project is distributed as a local stdio MCP server through the Python
package `powerbi-mcp-server-540`.

## One-Time Setup

1. Create the GitHub repository.
2. Add the remote locally:

   ```bash
   git remote add origin https://github.com/dbru540/powerbi-mcp-server.git
   ```

3. Add the real GitHub URLs to `pyproject.toml`:

   ```toml
   [project.urls]
   Homepage = "https://github.com/dbru540/powerbi-mcp-server"
   Repository = "https://github.com/dbru540/powerbi-mcp-server"
   Issues = "https://github.com/dbru540/powerbi-mcp-server/issues"
   ```

4. Create the TestPyPI pending publisher for `powerbi-mcp-server-540`.
5. Configure TestPyPI Trusted Publishing:

   - Publisher: GitHub
   - Owner: `dbru540`
   - Repository: `powerbi-mcp-server`
   - Workflow: `publish.yml`
   - Environment: `testpypi`

6. Configure PyPI Trusted Publishing for `powerbi-mcp-server-540` with:

   - Publisher: GitHub
   - Owner: `dbru540`
   - Repository: `powerbi-mcp-server`
   - Workflow: `publish.yml`
   - Environment: `pypi`

7. GitHub repository environments `pypi` and `testpypi` must exist. They were
   created for `dbru540/powerbi-mcp-server` on 2026-06-10.

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
C:/_pbimcp_pkg_install_venv/Scripts/python.exe -m pip install dist/powerbi_mcp_server_540-0.1.2-py3-none-any.whl
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-server-540.exe --help
C:/_pbimcp_pkg_install_venv/Scripts/powerbi-mcp-doctor.exe --project example --no-validate
```

Verify `uvx` behavior:

```bash
uvx --from dist/powerbi_mcp_server_540-0.1.2-py3-none-any.whl powerbi-mcp-server-540 --help
```

## Publish to TestPyPI

Run the GitHub Actions workflow manually:

```text
Actions -> Publish Python Package -> Run workflow -> target: testpypi
```

Then verify install:

```bash
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ powerbi-mcp-server-540 --help
```

## Publish to PyPI

Create and publish a GitHub release. The `publish.yml` workflow publishes the
built distributions to PyPI through Trusted Publishing.

Verify public install:

```bash
uvx powerbi-mcp-server-540 --help
powerbi-mcp-doctor
```

## Client Setup After Publication

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx powerbi-mcp-server-540
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx powerbi-mcp-server-540
```

## GitHub-Only Distribution

If PyPI is not ready yet, publish a GitHub tag and install directly from Git:

```bash
uvx --from git+https://github.com/dbru540/powerbi-mcp-server.git@v0.1.2 powerbi-mcp-server-540 --help
```

Claude Code:

```bash
claude mcp add --transport stdio powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-server.git@v0.1.2 powerbi-mcp-server-540
```

Codex:

```bash
codex mcp add powerbi-mcp -- uvx --from git+https://github.com/dbru540/powerbi-mcp-server.git@v0.1.2 powerbi-mcp-server-540
```

## Known Local Blockers

TestPyPI Trusted Publishing must still be configured from an authenticated
TestPyPI account before TestPyPI publication can succeed. The attempted GitHub
Actions run `27293576102` failed with `invalid-publisher` for the old package
name, but the same publisher claims apply to the renamed package:

```text
repo:dbru540/powerbi-mcp-server:environment:testpypi
```

Production PyPI should use the renamed package `powerbi-mcp-server-540` because
`powerbi-mcp-server` is already registered by another account. GitHub-only
distribution is available from the tagged repository.

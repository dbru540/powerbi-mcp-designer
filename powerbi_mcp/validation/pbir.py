from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from powerbi_mcp.validation.report import ValidationIssue, ValidationReport

_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_INDEX_PATH = _SCHEMAS_DIR / "INDEX.json"

# Module-level cache: schema URL -> loaded schema dict
_schema_cache: dict[str, dict[str, Any]] = {}
_index: dict[str, str] | None = None
_registry: Registry | None = None


def _load_index() -> dict[str, str]:
    global _index
    if _index is None:
        with _INDEX_PATH.open(encoding="utf-8") as f:
            _index = json.load(f)
    return _index


def _load_schema_by_url(schema_url: str) -> dict[str, Any] | None:
    """Return the vendored schema dict for the given URL, or None if unknown."""
    if schema_url in _schema_cache:
        return _schema_cache[schema_url]

    index = _load_index()
    filename = index.get(schema_url)
    if filename is None:
        return None

    schema_path = (_SCHEMAS_DIR / filename).resolve()
    if not schema_path.is_relative_to(_SCHEMAS_DIR.resolve()):
        return None  # refuse to load paths that escape the schemas directory
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)

    _schema_cache[schema_url] = schema
    return schema


def _build_registry() -> Registry:
    """Build a referencing.Registry pre-populated with all vendored schemas.

    Any $ref that cannot be resolved in the registry is answered with an
    empty (permissive) schema so that relative sub-schema references inside
    Microsoft's schemas do not trigger remote HTTP fetches.
    """
    global _registry
    if _registry is not None:
        return _registry

    index = _load_index()
    resources: list[tuple[str, Resource[Any]]] = []
    for url, filename in index.items():
        schema = _load_schema_by_url(url)
        if schema is not None:
            resources.append((url, DRAFT7.create_resource(schema)))

    def retrieve_permissive(uri: str) -> Resource[Any]:
        # Return a permissive empty schema for any ref not in our vendored set
        return DRAFT7.create_resource({})

    _registry = Registry(retrieve=retrieve_permissive).with_resources(resources)
    return _registry


def validate_pbir_payload(payload: dict[str, Any], file_path: str) -> ValidationReport:
    """Validate a PBIR JSON payload against the matching vendored Microsoft schema.

    Returns a ValidationReport with:
    - ok=True + PBIR_NO_SCHEMA info issue when no $schema field is present
    - ok=False + PBIR_UNKNOWN_SCHEMA error when $schema is not in INDEX.json
    - ok=False + PBIR_SCHEMA_VIOLATION errors when schema validation fails
    - ok=True (no issues) when everything is valid
    """
    schema_url: str | None = payload.get("$schema")

    if schema_url is None:
        return ValidationReport(
            ok=True,
            issues=[
                ValidationIssue(
                    severity="info",
                    code="PBIR_NO_SCHEMA",
                    message="No $schema field found; schema validation was skipped.",
                    path=file_path,
                    pointer=None,
                )
            ],
        )

    schema = _load_schema_by_url(schema_url)
    if schema is None:
        return ValidationReport(
            ok=False,
            issues=[
                ValidationIssue(
                    severity="error",
                    code="PBIR_UNKNOWN_SCHEMA",
                    message=(
                        f"Unknown $schema URL '{schema_url}'. "
                        "Run refresh_pbir_schemas.py to update the vendored schemas."
                    ),
                    path=file_path,
                    pointer=None,
                )
            ],
        )

    registry = _build_registry()
    validator = jsonschema.Draft7Validator(schema, registry=registry)
    issues: list[ValidationIssue] = []
    for error in validator.iter_errors(payload):
        pointer = "/" + "/".join(str(p) for p in error.absolute_path) if error.absolute_path else None
        issues.append(
            ValidationIssue(
                severity="error",
                code="PBIR_SCHEMA_VIOLATION",
                message=error.message,
                path=file_path,
                pointer=pointer,
            )
        )

    return ValidationReport(ok=len(issues) == 0, issues=issues)


def validate_pbir_file(file_path: str | Path) -> ValidationReport:
    """Read a PBIR JSON file and validate it against the matching vendored schema."""
    path = Path(file_path)

    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return ValidationReport(
            ok=False,
            issues=[
                ValidationIssue(
                    severity="error",
                    code="PBIR_FILE_NOT_FOUND",
                    message=f"File not found: {file_path}",
                    path=str(file_path),
                    pointer=None,
                )
            ],
        )
    except json.JSONDecodeError as exc:
        return ValidationReport(
            ok=False,
            issues=[
                ValidationIssue(
                    severity="error",
                    code="PBIR_PARSE_ERROR",
                    message=f"JSON parse error in {file_path}: {exc}",
                    path=str(file_path),
                    pointer=None,
                )
            ],
        )

    return validate_pbir_payload(payload, str(file_path))

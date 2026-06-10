"""Download and vendor Microsoft PBIR/Fabric JSON schemas used by the validation layer."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

SCHEMA_URLS = [
    "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.2.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.8.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/report/localSettings/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/editorSettings/1.0.0/schema.json",
    "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/localSettings/1.1.0/schema.json",
]

SCHEMAS_DIR = Path(__file__).parent.parent / "powerbi_mcp" / "validation" / "schemas"


def url_to_filename(url: str) -> str:
    path = url.replace("https://developer.microsoft.com/json-schemas/", "")
    return path.replace("/", "__")


def fetch_schema(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "powerbi-mcp-schema-refresh/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed official schema URLs only.
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def main() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, str] = {}

    for url in SCHEMA_URLS:
        filename = url_to_filename(url)
        dest = SCHEMAS_DIR / filename
        print(f"Fetching {url} ...")
        try:
            schema = fetch_schema(url)
            dest.write_text(json.dumps(schema, indent=2), encoding="utf-8", newline="\n")
            index[url] = filename
            print(f"  -> {filename}")
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)

    index_path = SCHEMAS_DIR / "INDEX.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8", newline="\n")
    print(f"\nWrote {len(index)} entries to {index_path}")

    if len(index) < len(SCHEMA_URLS):
        print(f"WARNING: only {len(index)}/{len(SCHEMA_URLS)} schemas downloaded", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

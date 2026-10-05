"""Read-only, script-free API reference for the public portfolio deployment."""

from __future__ import annotations

from html import escape
from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def render_api_reference(schema: dict[str, Any]) -> str:
    """Render route metadata only; never execute requests or display stored data."""
    title = escape(str(schema.get("info", {}).get("title", "API")))
    rows = []
    for path, operations in sorted(schema.get("paths", {}).items()):
        for method, operation in sorted(operations.items()):
            if method not in HTTP_METHODS:
                continue
            summary = escape(str(operation.get("summary", "")))
            protected = operation.get("security", schema.get("security", []))
            access = "Authentication required" if protected else "Public"
            rows.append(
                "<tr>"
                f"<td><code>{escape(method.upper())}</code></td>"
                f"<td><code>{escape(path)}</code></td>"
                f"<td>{summary}</td><td>{access}</td>"
                "</tr>"
            )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title} - API reference</title>"
        "<style>body{font:16px system-ui,sans-serif;margin:2rem auto;padding:0 1rem;"
        "max-width:1100px;color:#182638}h1{color:#194678}table{border-collapse:collapse;"
        "width:100%}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #ddd}"
        "code{overflow-wrap:anywhere}.table-wrap{overflow-x:auto}</style></head><body>"
        f"<h1>{title}</h1><p>Read-only API reference for a synthetic portfolio demo."
        " Protected operations require valid credentials.</p>"
        '<p><a href="/api/v1/health">Health</a> | '
        '<a href="/api/v1/products">Products JSON</a></p>'
        '<div class="table-wrap"><table><thead><tr><th>Method</th><th>Path</th>'
        "<th>Summary</th><th>Access</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></body></html>"
    )

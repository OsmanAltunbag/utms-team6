"""
Jinja2 email template rendering — SPEC-020.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

TEMPLATE_MARKER = "__template__"


def render_template(template_name: str, variables: dict[str, Any]) -> str:
    """Render a named template wrapped in the base layout."""
    inner = _env.get_template(f"{template_name}.html").render(**variables)
    return _env.get_template("base.html").render(
        title=variables.get("title", "UTMS Bildirimi"),
        body_content=inner,
    )


def parse_notification_body(body: str) -> tuple[Optional[str], dict[str, Any], str]:
    """
    Return (template_name, template_vars, plain_body).
    If body is JSON with __template__, use template rendering; otherwise plain text/HTML.
    """
    try:
        data = json.loads(body)
        if isinstance(data, dict) and TEMPLATE_MARKER in data:
            template_name = data.pop(TEMPLATE_MARKER)
            return template_name, data, ""
    except (json.JSONDecodeError, TypeError):
        pass
    return None, {}, body


def build_templated_body(template_name: str, **variables: Any) -> str:
    """Serialize template payload for storage in notifications.body."""
    payload = {TEMPLATE_MARKER: template_name, **variables}
    return json.dumps(payload, default=str)

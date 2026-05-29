from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_email(template_name: str, context: dict) -> str:
    """Render a notification email using a content template wrapped in base.html."""
    ctx = {"title": context.get("title", "UTMS Notification"), **context}
    content = _env.get_template(template_name).render(**ctx)
    return _env.get_template("base.html").render(content=content, title=ctx["title"])

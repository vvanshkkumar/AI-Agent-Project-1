import uuid
from datetime import date
from pathlib import Path

from api.blog.graph import get_blog_app
from api.blog.schemas import Plan
from api.blog.state import BlogState
from api.blog.storage import find_markdown_file, get_preview_url, get_run_workspace, get_markdown_url
from api.blog.text_utils import safe_slug


def run_blog_generation(topic: str) -> dict:
    run_id = uuid.uuid4().hex
    workspace = get_run_workspace(run_id)
    workspace.mkdir(parents=True, exist_ok=True)

    initial: BlogState = {
        "topic": topic,
        "run_id": run_id,
        "workspace_dir": str(workspace),
        "as_of": date.today().isoformat(),
        "sections": [],
        "expected_section_count": 0,
        "evidence": [],
        "queries": [],
        "mode": "closed_book",
        "needs_research": False,
        "plan": None,
        "recency_days": 3650,
        "merged_md": "",
        "md_with_placeholders": "",
        "image_specs": [],
        "final": "",
    }

    result = get_blog_app().invoke(initial)
    plan = result.get("plan")
    title = plan.blog_title if isinstance(plan, Plan) else None

    md_path: Path | None = workspace / f"{safe_slug(title or 'blog')}.md"
    if not md_path.exists():
        md_path = find_markdown_file(run_id)

    return {
        "run_id": run_id,
        "workspace_dir": str(workspace),
        "markdown": result.get("final", ""),
        "blog_title": title,
        "mode": result.get("mode"),
        "needs_research": result.get("needs_research"),
        "md_file": str(md_path) if md_path and md_path.exists() else None,
        "markdown_url": get_markdown_url(run_id),
        "preview_url": get_preview_url(run_id),
    }

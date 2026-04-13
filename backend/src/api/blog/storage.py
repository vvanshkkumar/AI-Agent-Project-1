from pathlib import Path

from fastapi import HTTPException

from api.blog.config import get_blog_output_root


def get_run_workspace(run_id: str) -> Path:
    return get_blog_output_root() / run_id


def find_markdown_file(run_id: str) -> Path | None:
    workspace = get_run_workspace(run_id)
    if not workspace.exists():
        return None
    files = sorted(workspace.glob("*.md"))
    return files[0] if files else None


def get_markdown_url(run_id: str) -> str:
    return f"/api/blog/runs/{run_id}/markdown"


def get_preview_url(run_id: str) -> str:
    return f"/api/blog/runs/{run_id}/preview"


def get_asset_url(run_id: str, relative_path: str) -> str:
    cleaned = relative_path.lstrip("/")
    return f"/api/blog/runs/{run_id}/assets/{cleaned}"


def resolve_run_asset_path(run_id: str, asset_path: str) -> Path:
    workspace = get_run_workspace(run_id).resolve()
    candidate = (workspace / asset_path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    return candidate

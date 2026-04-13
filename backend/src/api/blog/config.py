import os
from pathlib import Path

from settings import get_project_root, load_project_env


def get_blog_output_root() -> Path:
    """Base directory for blog runs (each request uses a subfolder by run_id)."""
    load_project_env()
    raw = os.environ.get("BLOG_OUTPUT_DIR", "data/blog_runs")
    path = Path(raw)
    if path.is_absolute():
        return path
    return (get_project_root() / path).resolve()

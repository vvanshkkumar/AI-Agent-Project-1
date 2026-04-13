import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from api.blog.presentation import render_markdown_html
from api.blog.storage import find_markdown_file, get_asset_url, resolve_run_asset_path
from api.myEmailer.sender import send_mail

RUN_MARKER_PREFIX = "__BLOG_RUN_ID__:"


def read_run_markdown(run_id: str) -> str:
    md_file = find_markdown_file(run_id)
    if md_file is None or not md_file.exists():
        raise HTTPException(status_code=404, detail="Blog run not found")
    return md_file.read_text(encoding="utf-8")


def build_schedule_body(run_id: str, markdown_text: str) -> str:
    return f"{RUN_MARKER_PREFIX}{run_id}\n\n{markdown_text}"


def extract_scheduled_run(body: str) -> tuple[str | None, str]:
    if body.startswith(RUN_MARKER_PREFIX):
        first_line, _, rest = body.partition("\n")
        run_id = first_line.removeprefix(RUN_MARKER_PREFIX).strip()
        return run_id or None, rest.lstrip()
    return None, body


def _build_inline_assets(run_id: str, html_content: str) -> tuple[str, list[dict[str, str | bytes]]]:
    asset_prefix = f"/api/blog/runs/{run_id}/assets/"
    seen: dict[str, str] = {}
    inline_assets: list[dict[str, str | bytes]] = []
    updated_html = html_content

    matches = re.findall(r'src="([^"]+)"', html_content)
    for src in matches:
        if not src.startswith(asset_prefix):
            continue
        if src in seen:
            updated_html = updated_html.replace(src, f"cid:{seen[src]}")
            continue

        asset_path = src.removeprefix(asset_prefix)
        file_path = resolve_run_asset_path(run_id, asset_path)
        if not file_path.exists() or not file_path.is_file():
            continue

        cid = f"blog-{uuid4().hex}"
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"

        inline_assets.append(
            {
                "cid": cid,
                "filename": file_path.name,
                "maintype": maintype,
                "subtype": subtype,
                "data": file_path.read_bytes(),
            }
        )
        seen[src] = cid
        updated_html = updated_html.replace(src, f"cid:{cid}")

    return updated_html, inline_assets


def build_newsletter_email(run_id: str, markdown_text: str) -> tuple[str, list[dict[str, str | bytes]]]:
    html_content = render_markdown_html(run_id, markdown_text)
    return _build_inline_assets(run_id, html_content)


def send_existing_run_email(run_id: str, subject: str, to_email: str) -> None:
    markdown_text = read_run_markdown(run_id)
    html_content, inline_assets = build_newsletter_email(run_id, markdown_text)
    send_mail(
        subject=subject,
        content=markdown_text,
        to_email=to_email,
        html_content=html_content,
        inline_assets=inline_assets,
    )

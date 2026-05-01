from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import Session, select

from cache import (
    CacheUnavailableError,
    check_rate_limit,
    get_cached_preview,
    set_cached_preview,
)
from api.blog.db_models import ScheduledEmail
from api.blog.newsletter import build_schedule_body, read_run_markdown, send_existing_run_email
from api.blog.presentation import normalize_markdown_for_web, render_markdown_html
from api.blog.runtime import describe_blog_runtime
from api.blog.service import run_blog_generation
from api.blog.storage import find_markdown_file, resolve_run_asset_path
from api.myEmailer.sender import send_mail
from db import get_session
from observers.status import get_run_status
from settings import ConfigurationError, get_email_settings

router = APIRouter(prefix="/blog", tags=["blog"])


class BlogGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    send_now: bool = False
    to_email: str | None = None
    email_subject: str | None = None
    schedule_at: datetime | None = None


class ExistingBlogEmailRequest(BaseModel):
    run_id: str = Field(..., min_length=8)
    to_email: str
    email_subject: str | None = None


class ExistingBlogScheduleRequest(ExistingBlogEmailRequest):
    schedule_at: datetime


@router.post("/generate")
def generate_blog(
    request: Request,
    payload: BlogGenerateRequest,
    session: Session = Depends(get_session),
):
    client_key = _client_key(request)
    try:
        rate_limit = check_rate_limit(client_key)
    except CacheUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "Rate limit exceeded: "
                f"max {rate_limit.limit} blog generations per "
                f"{rate_limit.window_seconds} seconds"
            ),
        )

    if payload.send_now and not payload.to_email:
        raise HTTPException(status_code=400, detail="to_email is required when send_now is true")
    if payload.schedule_at is not None and not payload.to_email:
        raise HTTPException(status_code=400, detail="to_email is required when schedule_at is set")

    try:
        if payload.send_now or payload.schedule_at is not None:
            get_email_settings()
        result = run_blog_generation(payload.topic)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Blog generation failed: {exc}") from exc
    md = result["markdown"]
    title = result.get("blog_title") or "Blog"
    subject = payload.email_subject or str(title)

    if payload.send_now:
        try:
            send_mail(subject=subject, content=md, to_email=payload.to_email)
            result["email_status"] = "sent"
        except Exception as e:
            result["email_status"] = "failed"
            result["email_error"] = str(e)
    else:
        result["email_status"] = "skipped"

    if payload.schedule_at is not None:
        run_at = payload.schedule_at
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        else:
            run_at = run_at.astimezone(timezone.utc)
        run_at_naive = run_at.replace(tzinfo=None)
        job = ScheduledEmail(
            to_email=payload.to_email,
            subject=subject,
            body=md,
            run_at=run_at_naive,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        result["scheduled_id"] = job.id
        result["scheduled_for"] = job.run_at.isoformat() + "Z"

    return result


@router.post("/send-existing")
def send_existing_blog(payload: ExistingBlogEmailRequest):
    subject = payload.email_subject or f"Newsletter: {payload.run_id}"
    try:
        get_email_settings()
        send_existing_run_email(payload.run_id, subject, payload.to_email)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Existing blog email failed: {exc}") from exc

    return {
        "run_id": payload.run_id,
        "to_email": payload.to_email,
        "email_subject": subject,
        "email_status": "sent",
    }


@router.post("/schedule-existing")
def schedule_existing_blog(
    payload: ExistingBlogScheduleRequest,
    session: Session = Depends(get_session),
):
    subject = payload.email_subject or f"Newsletter: {payload.run_id}"
    try:
        get_email_settings()
        markdown_text = read_run_markdown(payload.run_id)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise

    run_at = payload.schedule_at
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)
    else:
        run_at = run_at.astimezone(timezone.utc)
    run_at_naive = run_at.replace(tzinfo=None)

    job = ScheduledEmail(
        to_email=payload.to_email,
        subject=subject,
        body=build_schedule_body(payload.run_id, markdown_text),
        run_at=run_at_naive,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    return {
        "run_id": payload.run_id,
        "scheduled_id": job.id,
        "to_email": payload.to_email,
        "email_subject": subject,
        "scheduled_for": job.run_at.isoformat() + "Z",
        "email_status": "scheduled",
    }


@router.get("/scheduled")
def list_scheduled(session: Session = Depends(get_session), limit: int = 50):
    stmt = select(ScheduledEmail).order_by(desc(ScheduledEmail.run_at)).limit(limit)
    return list(session.exec(stmt).all())


@router.get("/runtime")
def blog_runtime():
    return describe_blog_runtime()


@router.get("/runs/{run_id}/status")
def blog_run_status(run_id: str):
    return get_run_status(run_id)


@router.get("/runs/{run_id}/markdown", response_class=PlainTextResponse)
def get_blog_markdown(run_id: str):
    md_file = find_markdown_file(run_id)
    if md_file is None or not md_file.exists():
        raise HTTPException(status_code=404, detail="Blog run not found")
    content = md_file.read_text(encoding="utf-8")
    normalized = normalize_markdown_for_web(run_id, content)
    return PlainTextResponse(normalized, media_type="text/markdown; charset=utf-8")


@router.get("/runs/{run_id}/preview", response_class=HTMLResponse)
def preview_blog(run_id: str):
    cached = get_cached_preview(run_id)
    if cached:
        return HTMLResponse(cached)

    md_file = find_markdown_file(run_id)
    if md_file is None or not md_file.exists():
        raise HTTPException(status_code=404, detail="Blog run not found")
    content = md_file.read_text(encoding="utf-8")
    html = render_markdown_html(run_id, content)
    set_cached_preview(run_id, html)
    return HTMLResponse(html)


@router.get("/runs/{run_id}/assets/{asset_path:path}")
def get_blog_asset(run_id: str, asset_path: str):
    file_path = resolve_run_asset_path(run_id, asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(Path(file_path))


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlmodel import Session, select

from api.blog.db_models import FailedJob, ScheduledEmail
from db import get_session
from tasks.email_tasks import send_scheduled_email

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/failed")
def list_failed_jobs(
    session: Session = Depends(get_session),
    limit: int = 50,
):
    stmt = select(FailedJob).order_by(desc(FailedJob.failed_at)).limit(limit)
    return list(session.exec(stmt).all())


@router.post("/failed/{job_id}/retry")
def retry_failed_job(
    job_id: int,
    session: Session = Depends(get_session),
):
    failed_job = session.get(FailedJob, job_id)
    if failed_job is None:
        raise HTTPException(status_code=404, detail="Failed job not found")
    if failed_job.task_name != "tasks.email_tasks.send_scheduled_email":
        raise HTTPException(status_code=400, detail="Unsupported failed job type")
    if failed_job.entity_id is None:
        raise HTTPException(status_code=400, detail="Failed job has no scheduled email id")

    scheduled_email = session.get(ScheduledEmail, failed_job.entity_id)
    if scheduled_email is None:
        raise HTTPException(status_code=404, detail="Scheduled email not found")
    if scheduled_email.status == "sent":
        raise HTTPException(status_code=409, detail="Scheduled email is already sent")

    scheduled_email.status = "queued"
    scheduled_email.error_message = None
    failed_job.status = "requeued"
    failed_job.requeued_at = datetime.utcnow()
    session.add(scheduled_email)
    session.add(failed_job)
    session.commit()

    task = send_scheduled_email.delay(scheduled_email.id)
    return {
        "status": "requeued",
        "failed_job_id": failed_job.id,
        "scheduled_email_id": scheduled_email.id,
        "task_id": task.id,
    }

import json
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from api.blog.db_models import FailedJob, ScheduledEmail
from api.blog.newsletter import build_newsletter_email, extract_scheduled_run, read_run_markdown
from api.myEmailer.sender import send_mail
from celery_app import celery_app
from db import get_engine, init_db

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.email_tasks.dispatch_due_emails")
def dispatch_due_emails() -> dict:
    init_db()
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    dispatched = 0

    with Session(get_engine()) as session:
        stmt = select(ScheduledEmail).where(
            ScheduledEmail.status == "pending",
            ScheduledEmail.run_at <= now_naive,
        )
        due_emails = list(session.exec(stmt).all())

        for email in due_emails:
            email.status = "queued"
            email.error_message = None
            session.add(email)
            session.commit()
            session.refresh(email)
            send_scheduled_email.delay(email.id)
            dispatched += 1

    logger.info(
        json.dumps(
            {
                "event": "due_scheduled_emails_dispatched",
                "dispatched": dispatched,
            }
        )
    )
    return {"dispatched": dispatched}


@celery_app.task(
    bind=True,
    name="tasks.email_tasks.send_scheduled_email",
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_scheduled_email(self, scheduled_email_id: int) -> dict | None:
    init_db()
    with Session(get_engine()) as session:
        record = session.get(ScheduledEmail, scheduled_email_id)
        if record is None:
            logger.error(
                json.dumps(
                    {
                        "event": "scheduled_email_missing",
                        "scheduled_email_id": scheduled_email_id,
                    }
                )
            )
            return None

        if record.status == "sent":
            return {"status": "already_sent", "scheduled_email_id": scheduled_email_id}

        attempt = int(self.request.retries) + 1
        try:
            record.status = "running"
            record.error_message = None
            session.add(record)
            session.commit()

            run_id, body = extract_scheduled_run(record.body)
            if run_id:
                markdown_text = read_run_markdown(run_id)
                html_content, inline_assets = build_newsletter_email(run_id, markdown_text)
                send_mail(
                    subject=record.subject,
                    content=markdown_text,
                    to_email=record.to_email,
                    html_content=html_content,
                    inline_assets=inline_assets,
                )
            else:
                send_mail(
                    subject=record.subject,
                    content=body,
                    to_email=record.to_email,
                )

            record.status = "sent"
            record.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
            record.error_message = None
            session.add(record)
            session.commit()

            logger.info(
                json.dumps(
                    {
                        "event": "scheduled_email_sent",
                        "scheduled_email_id": scheduled_email_id,
                        "attempt": attempt,
                    }
                )
            )
            return {"status": "sent", "scheduled_email_id": scheduled_email_id}
        except Exception as exc:
            logger.warning(
                json.dumps(
                    {
                        "event": "scheduled_email_send_failed",
                        "scheduled_email_id": scheduled_email_id,
                        "attempt": attempt,
                        "error": str(exc),
                    }
                )
            )

            if self.request.retries >= self.max_retries:
                record.status = "failed"
                record.error_message = str(exc)[:2000]
                failed = FailedJob(
                    task_id=str(self.request.id),
                    task_name="tasks.email_tasks.send_scheduled_email",
                    entity_id=scheduled_email_id,
                    error_message=str(exc)[:4000],
                    attempts=attempt,
                    payload={"scheduled_email_id": scheduled_email_id},
                    status="open",
                )
                session.add(record)
                session.add(failed)
                session.commit()
                logger.error(
                    json.dumps(
                        {
                            "event": "scheduled_email_dead_lettered",
                            "scheduled_email_id": scheduled_email_id,
                            "failed_job_id": failed.id,
                            "attempt": attempt,
                        }
                    )
                )
                return {"status": "failed", "scheduled_email_id": scheduled_email_id}

            record.status = "retrying"
            record.error_message = str(exc)[:2000]
            session.add(record)
            session.commit()
            countdown = 60 * (2 ** int(self.request.retries))
            raise self.retry(exc=exc, countdown=countdown)

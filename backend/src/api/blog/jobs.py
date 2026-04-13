from datetime import datetime, timezone

from sqlmodel import Session, select

from api.blog.db_models import ScheduledEmail
from api.blog.newsletter import build_newsletter_email, extract_scheduled_run, read_run_markdown
from api.myEmailer.sender import send_mail
from db import get_engine


def process_due_scheduled_emails() -> None:
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(get_engine()) as session:
        stmt = select(ScheduledEmail).where(
            ScheduledEmail.status == "pending",
            ScheduledEmail.run_at <= now_naive,
        )
        rows = list(session.exec(stmt).all())
        for row in rows:
            try:
                run_id, body = extract_scheduled_run(row.body)
                if run_id:
                    markdown_text = read_run_markdown(run_id)
                    html_content, inline_assets = build_newsletter_email(run_id, markdown_text)
                    send_mail(
                        subject=row.subject,
                        content=markdown_text,
                        to_email=row.to_email,
                        html_content=html_content,
                        inline_assets=inline_assets,
                    )
                else:
                    send_mail(subject=row.subject, content=body, to_email=row.to_email)
                row.status = "sent"
                row.error_message = None
            except Exception as e:
                row.status = "failed"
                row.error_message = str(e)[:2000]
            session.add(row)
        session.commit()

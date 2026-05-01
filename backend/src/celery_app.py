import os

from celery import Celery

from settings import load_project_env

load_project_env()

REDIS_URL = os.environ.get("REDIS_URL") or "redis://redis:6379/0"

celery_app = Celery(
    "ai_agent_project",
    broker=REDIS_URL,
    backend=REDIS_URL.replace("/0", "/1"),
    include=["tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "dispatch-due-emails": {
            "task": "tasks.email_tasks.dispatch_due_emails",
            "schedule": 60.0,
        },
    },
)

from apscheduler.schedulers.background import BackgroundScheduler

from api.blog.jobs import process_due_scheduled_emails

_scheduler: BackgroundScheduler | None = None


def start_blog_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        process_due_scheduled_emails,
        "interval",
        seconds=60,
        id="blog_scheduled_emails",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched


def stop_blog_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

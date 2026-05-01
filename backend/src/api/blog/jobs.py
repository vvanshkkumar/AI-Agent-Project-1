from tasks.email_tasks import dispatch_due_emails


def process_due_scheduled_emails() -> dict:
    task = dispatch_due_emails.delay()
    return {"task_id": task.id, "status": "queued"}

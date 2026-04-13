from datetime import datetime

from sqlmodel import Field, SQLModel


class ScheduledEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    to_email: str
    subject: str
    body: str
    run_at: datetime
    status: str = Field(default="pending")
    error_message: str | None = None

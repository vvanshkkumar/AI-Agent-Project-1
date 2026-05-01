from datetime import datetime

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class ScheduledEmail(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    to_email: str
    subject: str
    body: str
    run_at: datetime
    status: str = Field(default="pending")
    error_message: str | None = None
    sent_at: datetime | None = None


class PipelineEvent(SQLModel, table=True):
    __tablename__ = "pipeline_events"

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    node_name: str
    status: str
    meta: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class FailedJob(SQLModel, table=True):
    __tablename__ = "failed_jobs"

    id: int | None = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    task_name: str = Field(index=True)
    entity_id: int | None = Field(default=None, index=True)
    error_message: str | None = None
    attempts: int = Field(default=1)
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="open", index=True)
    failed_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    requeued_at: datetime | None = None


class SectionAttempt(SQLModel, table=True):
    __tablename__ = "section_attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "task_id", name="uq_section_attempt_run_task"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    task_id: int = Field(index=True)
    status: str = Field(default="PENDING", index=True)
    attempts: int = Field(default=0)
    last_attempt_at: datetime | None = None
    error_message: str | None = None

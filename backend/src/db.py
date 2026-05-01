from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from settings import get_database_url

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url = get_database_url()
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        _engine = create_engine(database_url, connect_args=connect_args)
    return _engine

def init_db():
    from api.blog.db_models import FailedJob, PipelineEvent, ScheduledEmail  # noqa: F401
    from api.chat.db_models import ChatMessage  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_column(engine, ScheduledEmail.__tablename__, "sent_at", "TIMESTAMP")


def _ensure_column(engine: Engine, table_name: str, column_name: str, column_type: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

def get_session():
    with Session(get_engine()) as session:
        yield session

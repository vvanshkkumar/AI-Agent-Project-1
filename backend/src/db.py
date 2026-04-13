from sqlalchemy.engine import Engine
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
    from api.blog.db_models import ScheduledEmail  # noqa: F401
    from api.chat.db_models import ChatMessage  # noqa: F401

    SQLModel.metadata.create_all(get_engine())

def get_session():
    with Session(get_engine()) as session:
        yield session

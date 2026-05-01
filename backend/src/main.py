from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.blog.routing import router as blog_router
from api.chat.routing import router as chat_router
from api.jobs.routing import router as jobs_router
from db import init_db
from observers.audit_log_observer import AuditLogObserver
from observers.publisher import publisher
from observers.redis_status_observer import RedisStatusObserver
from observers.structured_log_observer import StructuredLogObserver
from settings import load_project_env

load_project_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    publisher.attach(AuditLogObserver())
    publisher.attach(RedisStatusObserver())
    publisher.attach(StructuredLogObserver())
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
app.include_router(blog_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")


@app.get("/")
async def read_root():
    return {"message": "Hello World"}

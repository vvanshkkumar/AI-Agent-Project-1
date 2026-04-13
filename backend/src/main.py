from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.blog.routing import router as blog_router
from api.blog.scheduler import start_blog_scheduler, stop_blog_scheduler
from api.chat.routing import router as chat_router
from db import init_db
from settings import load_project_env

load_project_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_blog_scheduler()
    try:
        yield
    finally:
        stop_blog_scheduler()


app = FastAPI(lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
app.include_router(blog_router, prefix="/api")


@app.get("/")
async def read_root():
    return {"message": "Hello World"}

from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_db
from api.chat.routing import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(chat_router,prefix="/api")

@app.get("/")
async def read_root():
    return {"message": "Hello World"}
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_db, get_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "Hello World"}
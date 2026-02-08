from app.core.logging import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.playlist_service import router as playlist_router
from app.services.settings_service import router as settings_router
from app.core.db import create_db_and_tables
from contextlib import asynccontextmanager

setup_logging(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1",
]

app.include_router(playlist_router)
app.include_router(settings_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

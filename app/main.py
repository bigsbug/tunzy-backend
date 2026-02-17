import asyncio
from sqlmodel import select
from app.core import config
from app.core.logging import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.download_manager.manager import DownloadManager
from app.models.settings import SettingsModel
from app.services.playlist_service import router as playlist_router
from app.services.settings_service import router as settings_router
from app.services.download_service import router as downloads_router
from app.services.player_service import router as player_router
from app.core.db import create_db_and_tables, get_session
from contextlib import asynccontextmanager

setup_logging(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    session = next(get_session())
    settings_query = select(SettingsModel)
    settings_obj = session.exec(settings_query).one_or_none()
    concurrent_downloads = getattr(
        settings_obj, "concurrent_downloads", config.settings.concurrent_downloads
    )
    app.state.downloader = DownloadManager(concurrent_downloads)
    asyncio.create_task(app.state.downloader.worker())
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
app.include_router(downloads_router)
app.include_router(player_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

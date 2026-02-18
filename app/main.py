import asyncio
from sqlmodel import select
from app.core import config
from app.core.logging import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.download_manager.manager import DownloadManager
from app.download_manager.utils import add_downloads_to_download_manager
from app.models.settings import SettingsModel
from app.services.playlist_service import router as playlist_router
from app.services.settings_service import router as settings_router
from app.services.download_service import router as downloads_router
from app.services.player_service import router as player_router
from app.services.frontend_service import router as frontend_router
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
    asyncio.create_task(
        add_downloads_to_download_manager(session, app.state.downloader)
    )
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1",
    "host.docker.internal",
]

app.include_router(prefix="/api", router=playlist_router)
app.include_router(prefix="/api", router=settings_router)
app.include_router(prefix="/api", router=downloads_router)
app.include_router(prefix="/api", router=player_router)
app.include_router(router=frontend_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

from asyncio import sleep
import json
import threading
from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder

from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter
from sqlmodel import select
from app.core.db import SessionDep
from app.core.logging import get_logger
from app.models.playlist import (
    DownloadTrackDataModel,
    DownloadTrackModel,
    DownloadTrackPublicModel,
    DownloadStatusEnum,
)
from app.models.playlist import TrackModel
from app.download_manager import soundcloud_downloader
router = APIRouter(prefix="/downloads")
logger = get_logger(__name__)

@router.get("/", response_model=list[DownloadTrackPublicModel])
async def downloads_list(orm: SessionDep):
    query = (
        select(DownloadTrackModel)
        .where(
            # DownloadTrackModel.status.not_in([DownloadStatusEnum.SUCCESSFUL])
        )
        .order_by(DownloadTrackModel.status)
    )
    items = orm.exec(query).fetchall()
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Items Not Found"
        )
    return items


@router.post("/{id}/cancel/", response_model=DownloadTrackDataModel)
async def cancel_download(id, orm: SessionDep, request: Request):
    query = select(DownloadTrackModel).where(DownloadTrackModel.id == id)
    item = orm.exec(query).one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item Not Found"
        )
    await request.app.state.downloader.cancel_download(item.id)
    orm.delete(item)
    orm.commit()
    return item

@router.post("/{id}/retry")
async def retry_download(orm: SessionDep): ...

@router.post(
    "/playlists/tracks/{track_id}",
    response_model=DownloadTrackDataModel,
)
async def download_track(track_id: int, orm: SessionDep, request: Request):
    track_query = select(TrackModel).where(TrackModel.id == track_id)
    track_obj = orm.exec(track_query).one_or_none()
    if not track_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track Not Found"
        )
    download_track_query = select(DownloadTrackModel).where(
        DownloadTrackModel.track_id == track_id
    )
    download_track_obj = orm.exec(download_track_query).one_or_none()
    if download_track_obj:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This Track Already Is Exists"
        )

    download_item = DownloadTrackModel(
        status=DownloadStatusEnum.PENDING,
        track_id=track_id,
        file_path=None,
    )
    orm.add(download_item)
    orm.commit()
    cancel_event = threading.Event()
    ctx = soundcloud_downloader.DownloadContext(
        progress_reports=request.app.state.downloader.progress_reports,
        cancel_event=cancel_event,
        download_object=download_item,
    )

    await request.app.state.downloader.add_to_queue(
        download_item.id,
        soundcloud_downloader.download(ctx, orm),  # type: ignore
        cancel_event,
        -1,
    )

    return download_item

@router.get("/progress-reports/")
async def download_progress_reports(request: Request):
    progress_reports = request.app.state.downloader.progress_reports

    async def progress_generator():
        last_report = {}
        while True:
            if await request.is_disconnected():
                break
            progresses = progress_reports.copy()
            # if last_report == progress_reports:
            #     continue

            last_report = progresses
            data = json.dumps(jsonable_encoder(progresses))
            yield f"data: {data}\n\n"
            await sleep(0.5)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.post("/playlists/{id}/tracks")
async def download_playlist(orm: SessionDep): ...

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
from app.download_manager.manager import DownloadProgressReport
from app.models.playlist import (
    DownloadTrackDataModel,
    DownloadTrackModel,
    DownloadTrackPublicModel,
    DownloadStatusEnum,
    PlaylistModel,
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
async def cancel_download(id: int, orm: SessionDep, request: Request):
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
async def retry_download(id: int, orm: SessionDep, request: Request):
    download_track_query = select(DownloadTrackModel).where(DownloadTrackModel.id == id)
    download_item = orm.exec(download_track_query).one_or_none()
    if not download_item:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Download Job Not Found"
        )

    download_item.status = DownloadStatusEnum.DOWNLOADING
    orm.add(download_item)
    orm.commit()
    cancel_event = threading.Event()
    ctx = soundcloud_downloader.DownloadContext(
        progress_reports=request.app.state.downloader.progress_reports,
        progress_event=request.app.state.downloader.progress_event,
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
        progress_event=request.app.state.downloader.progress_event,
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
async def download_progress_reports(
    request: Request,
):
    progress_reports: dict[int, DownloadProgressReport] = (
        request.app.state.downloader.progress_reports
    )

    async def progress_generator():
        while True:
            if await request.is_disconnected():
                break

            await request.app.state.downloader.progress_event.wait()
            request.app.state.downloader.progress_event.clear()

            progresses = progress_reports.copy()
            data = json.dumps(jsonable_encoder(progresses))

            yield f"data: {data}\n\n"
            await sleep(0.5)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.get("/progress-report/{playlist_id}/playlist")
async def download_playlist_progress_report(
    playlist_id: int, request: Request, orm: SessionDep
):
    progress_reports: dict[int, DownloadProgressReport] = (
        request.app.state.downloader.progress_reports
    )
    playlist_qs = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
    playlist_obj = orm.exec(playlist_qs).one_or_none()
    if not playlist_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist Not Found"
        )
    tracks_ids_lookup = set([obj.id for obj in playlist_obj.tracks])

    async def progress_generator(tracks_ids_lookup):
        while True:
            if await request.is_disconnected():
                break

            # Refresh items when this api start sooner then sync tracks API
            # if it be disabled it has a chance that don't show updated data
            if not tracks_ids_lookup:
                orm.refresh(playlist_obj)
                tracks_ids_lookup = set([obj.id for obj in playlist_obj.tracks])

            await request.app.state.downloader.progress_event.wait()
            request.app.state.downloader.progress_event.clear()

            current = progress_reports.copy()
            playlist_progress = {
                obj.track_id: obj
                for obj in current.values()
                if obj.track_id in tracks_ids_lookup
            }
            data = json.dumps(jsonable_encoder(playlist_progress))
            yield f"data: {data}\n\n"
            await sleep(0.5)

    return StreamingResponse(
        progress_generator(tracks_ids_lookup), media_type="text/event-stream"
    )


@router.post("/playlists/{id}/tracks")
async def download_playlist(orm: SessionDep): ...

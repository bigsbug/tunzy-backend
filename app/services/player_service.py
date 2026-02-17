from pathlib import Path
from fastapi import HTTPException, Request, status, Response
from fastapi.routing import APIRouter
from sqlmodel import select
from app.core import config
from app.core.db import SessionDep
from app.core.logging import get_logger
from app.models.playlist import DownloadStatusEnum, TrackModel
from fastapi.responses import StreamingResponse

from mimetypes import guess_type

logger = get_logger(__name__)
router = APIRouter(prefix="/player")


def file_streamer(file_path: Path, start: int, end: int, chunk_size: int):
    total_size = end - start
    logger.info(
        "Start Streaming File %s Range %d-%d Chunk-Size %d",
        file_path,
        start,
        end,
        chunk_size,
    )
    with open(file_path, "rb") as file:
        file.seek(start)
        while total_size >= 0:
            total_size -= min(chunk_size, chunk_size)
            chunk = file.read(min(chunk_size, chunk_size))
            yield chunk
    logger.info("Ended Streaming File :%s ", file_path)


@router.head("/{track_id}/play")
async def play_track_head(track_id: int, orm: SessionDep):
    track_query = select(TrackModel).where(TrackModel.id == track_id)
    track_obj = orm.exec(track_query).one_or_none()

    if not track_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track Not Found"
        )
    elif (
        not track_obj.download
        or not track_obj.download.file_path
        or track_obj.download.status != DownloadStatusEnum.SUCCESSFUL
    ):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY, detail="Track Is Not Downloaded Yet"
        )
    elif not Path(track_obj.download.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="File Not Found On The Disk",
        )

    file_path = track_obj.download.file_path
    file_size = Path(file_path).stat().st_size
    file_type, _ = guess_type(file_path)
    # fallback type when type can't find
    file_type = file_type or "application/octet-stream"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": file_type,
    }
    return Response(headers=headers, status_code=status.HTTP_200_OK)


@router.get("/{track_id}/play")
async def play_track(track_id: int, orm: SessionDep, request: Request):
    track_query = select(TrackModel).where(TrackModel.id == track_id)
    track_obj = orm.exec(track_query).one_or_none()
    if not track_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track Not Found"
        )
    elif (
        not track_obj.download
        or not track_obj.download.file_path
        or track_obj.download.status != DownloadStatusEnum.SUCCESSFUL
    ):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY, detail="Track Is Not Downloaded Yet"
        )
    elif not Path(track_obj.download.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="File Not Found On The Disk",
        )

    file_path = Path(track_obj.download.file_path)
    file_size: int = file_path.stat().st_size

    range_header = request.headers.get("range", "").lstrip("bytes=")
    if not range_header:
        start_range, end_range = 0, file_size - 1
    else:
        start_range, end_range = range_header.split("-")

        # browser can send empty range empty so we set fallback
        start_range = start_range or 0
        end_range = end_range or file_size - 1

        # parse to int
        start_range = int(start_range)
        end_range = int(end_range)

    # headers values
    file_type, _ = guess_type(file_path)
    # fallback type when type can't find
    file_type = file_type or "application/octet-stream"

    content_range = f"bytes {start_range}-{end_range}/{file_size}"

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": file_type,
        "Content-Range": content_range,
    }

    return StreamingResponse(
        status_code=status.HTTP_206_PARTIAL_CONTENT
        if range_header
        else status.HTTP_200_OK,
        headers=headers,
        content=file_streamer(
            file_path,
            start_range,
            end_range,
            config.settings.stream_chunk_size,
        ),
    )



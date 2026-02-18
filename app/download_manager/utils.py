import threading
from sqlmodel import Session, case, select
from app.core.logging import get_logger
from app.download_manager import soundcloud_downloader
from app.download_manager.manager import DownloadManager
from app.models.playlist import DownloadStatusEnum, DownloadTrackModel

logger = get_logger(__name__)


async def add_downloads_to_download_manager(
    orm: Session, download_manager: DownloadManager
):
    logger.info("start adding downloads to download manager")

    downloads_qs = (
        select(DownloadTrackModel)
        .where(
            DownloadTrackModel.status.in_(  # type: ignore
                [DownloadStatusEnum.PENDING, DownloadStatusEnum.DOWNLOADING]
            )
        )
        .order_by(
            case(
                (DownloadTrackModel.status == DownloadStatusEnum.DOWNLOADING, 0),
                (DownloadTrackModel.status == DownloadStatusEnum.PENDING, 1),
                else_=2,
            )
        )
    )
    downloads = orm.exec(downloads_qs).fetchall()

    for download in downloads:
        ctx = soundcloud_downloader.DownloadContext(
            progress_reports=download_manager.progress_reports,
            progress_event=download_manager.progress_event,
            cancel_event=threading.Event(),
            download_object=download,
        )
        await download_manager.add_to_queue(
            download.id or -1,
            soundcloud_downloader.download(ctx, orm),  # type: ignore
            ctx.cancel_event,
            -1,
        )

    logger.info(
        "downloads objects added to download manager total %d",
        len(downloads),
    )

    for download in downloads:
        download.status = DownloadStatusEnum.PENDING
    orm.commit()
    logger.info(
        "downloads object status [downloading, pending] changed to [pending] total %d",
        len(downloads),
    )

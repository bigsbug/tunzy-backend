import asyncio
from fastapi.routing import APIRouter
from sqlmodel import select
from app.core import config
from app.core.db import SessionDep
from app.core.logging import get_logger
from app.download_manager.manager import DownloadContext, DownloadProgressReport
from app.models.playlist import DownloadStatusEnum
from app.models.settings import SettingsModel
from app.soundcloud.download import sync_download_ytdl

router = APIRouter(prefix="/downloads")
logger = get_logger(__name__)

YTDL_STATUS_MAP = {
    "downloading": DownloadStatusEnum.DOWNLOADING,
    "failed": DownloadStatusEnum.FAILED,
    "finished": DownloadStatusEnum.SUCCESSFUL,
}



def error_logger(fn):
    def wrapper(*args, **kws):
        try:
            fn(*args, **kws)
        except Exception as err:
            logger.error("Error %s", err)

    return wrapper


@error_logger
def download_hook(dtl, ctx: DownloadContext):
    progress_reports: dict[int, DownloadProgressReport] = ctx.progress_reports
    download_id = ctx.download_object.id or -1

    if ctx.cancel_event.is_set():
        logger.info("Downloading Thread Is Canceled")
        raise asyncio.CancelledError()

    percent = dtl.get("_percent", 0)
    current_report = progress_reports.get(
        download_id,
        DownloadProgressReport(track_id=ctx.download_object.track_id),
    )
    current_report.percent = max(current_report.percent, int(percent))
    current_report.status = YTDL_STATUS_MAP.get(
        dtl.get("status"), DownloadStatusEnum.DOWNLOADING
    )
    progress_reports[download_id] = current_report

    if dtl.get("status") == "finished":
        ctx.file_path = dtl.get("filename")
        logger.info("File Path: %s", ctx.file_path)

    ctx.progress_event.set()
    logger.info(f"*** Progress: {current_report.percent} {current_report.status}")



class YtdlLogger:
    def debug(self, msg): ...

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        logger.error(msg)


async def download(ctx: DownloadContext, orm: SessionDep):
    logger.info("Start Downloading %d", ctx.download_object.id)
    ctx.download_object.status = DownloadStatusEnum.DOWNLOADING
    orm.add(ctx.download_object)
    orm.commit()

    setting_query = select(SettingsModel)
    setting = orm.exec(setting_query).one_or_none()
    concurrent_fragment_downloads = (
        setting.concurrent_fragment_downloads
        if setting
        else config.settings.concurrent_fragment_downloads
    )
    http_proxy = setting.http_proxy if setting else config.settings.http_proxy


    try:
        ydl_config = config.ydl_opts.copy()
        ydl_config["progress_hooks"] = [lambda d: download_hook(d, ctx)]
        ydl_config["logger"] = YtdlLogger()  # type: ignore
        ydl_config["concurrent_fragment_downloads"] = concurrent_fragment_downloads
        ydl_config["proxy"] = http_proxy or None

        await asyncio.create_task(
            asyncio.to_thread(
                sync_download_ytdl, [ctx.download_object.track.url or ""], ydl_config
            )
        )
        ctx.download_object.status = DownloadStatusEnum.SUCCESSFUL
        ctx.download_object.file_path = ctx.file_path
        orm.add(ctx.download_object)

        logger.info(
            "Downloading Done %d saved into %s",
            ctx.download_object.id,
            ctx.download_object.file_path,
        )

    except asyncio.CancelledError:
        logger.info("Download %d Canceled", ctx.download_object.id)
        ctx.download_object.status = DownloadStatusEnum.FAILED
        orm.add(ctx.download_object)

        current_report = ctx.progress_reports.get(
            ctx.download_object.id,
            DownloadProgressReport(track_id=ctx.download_object.track_id),
        )
        current_report.status = DownloadStatusEnum.FAILED
        ctx.progress_reports[ctx.download_object.id] = current_report

    except Exception as err:
        logger.error("exception when downloading %s", err)
        ctx.download_object.status = DownloadStatusEnum.FAILED
        orm.add(ctx.download_object)

        current_report = ctx.progress_reports.get(
            ctx.download_object.id,
            DownloadProgressReport(track_id=ctx.download_object.track_id),
        )
        current_report.status = DownloadStatusEnum.FAILED
        ctx.progress_reports[ctx.download_object.id] = current_report
    try:
        orm.commit()
    except Exception as ex:
        logger.error("Error on Committing %s", ex)
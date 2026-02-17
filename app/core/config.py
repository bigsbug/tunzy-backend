from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
from pathlib import Path

import yt_dlp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
DB_PATH = BASE_DIR / "sync_me.db"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    service_name: str
    logs_path: str = str(BASE_DIR / "logs")
    http_proxy: str
    soundcloud_oauth: str
    concurrent_downloads: int = 4  # 4–16 depending on your bandwidth
    concurrent_fragment_downloads: int = 1  # 4–16 depending on your bandwidth
    download_folder: str = str(BASE_DIR / "musics")
    file_template: str = "%(title)s.%(ext)s"
    download_retries: int = 4
    sync_interval: int = 30
    stream_chunk_size: int = 1024 * 1024  # 1 MB in bytes

    db_url: str = f"sqlite:///{DB_PATH}"

    @property
    def log_file(self) -> str:
        logs_file: str = str(Path(self.logs_path) / f"{self.service_name.lower()}.logs")
        return logs_file

    @property
    def output_download(self) -> str:
        return str(Path(self.download_folder) / self.file_template)


settings = Settings()  # type: ignore

ydl_opts: "yt_dlp._Params" = {
    "format": "bestaudio/best",
    "outtmpl": settings.output_download,  # e.g. 'downloads/%(title)s.%(ext)s'
    "quiet": False,
    "no_warnings": True,
    "continuedl": True,
    "retries": settings.download_retries,
    # Optional: force HLS if needed
    # 'extractor_args': {'soundcloud': {'formats': 'hls'}},
    # For faster segmented downloads:
    "concurrent_fragment_downloads": settings.concurrent_fragment_downloads,
    "proxy": settings.http_proxy,
}

# make dir of logs
logs_path = Path(settings.logs_path)
logs_path.mkdir(parents=True, exist_ok=True)

LOGGING: dict = {
    "version": 1,
    # https://docs.python.org/3/library/logging.config.html#logging-config-dict-incremental
    # "incremental": False,
    "disable_existing_loggers": False,
    "formatters": {
        # "formatter_ID": {
        #     # config of it
        #     "format": "",
        #     "datefmt": "",
        #     "style": "",
        #     "validate": "",
        #     "defaults": "",
        #     "class":"",
        # },
        "default": {
            # you need to use `service_name_provider` filter to access to `service` name
            "format": "%(asctime)s | %(levelname)s | %(service)s | %(name)s | %(message)s",
            # ISO-8601 format
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        }
    },
    "filters": {
        # "filter_ID": {
        #     # config of it
        #     "name": "",
        # },
        "service_name_provider": {
            "()": "app.core.logging.ServiceNameFilter",
            "service": settings.service_name,
        }
    },
    "handlers": {
        # "handler_ID": {
        #     # config of it
        #     "class": "",
        #     "level": "INFO",
        #     "formatter": "formatter_ID",
        #     "filters": [
        #         "filter_ID",
        #     ],
        #     "custom_keys_for_handler_instance": "value",
        # },
        "console": {
            "class": "logging.StreamHandler",
            "level": logging.INFO,
            "formatter": "default",
            "filters": [
                "service_name_provider",
            ],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": logging.INFO,
            "formatter": "default",
            "filters": [
                "service_name_provider",
            ],
            "filename": settings.log_file,
            # 1 MB of size
            "maxBytes": 1024 * 1024 * 1,
            "backupCount": 10,
        },
    },
    "loggers": {
        # "logger_name": {
        #     # config of it
        #     "level": "Warning",
        #     "propagate": False,
        #     "filters": [
        #         "filter_ID",
        #     ],
        #     "handlers": [
        #         "handler_ID",
        #     ],
        # },
    },
    "root": {
        # root (global) level config
        "level": logging.DEBUG,
        # "filters": [
        #     "filter_ID",
        # ],
        "handlers": [
            "console",
            "file",
        ],
    },
}


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript,text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "authorization": settings.soundcloud_oauth,
}

from pydantic_settings import BaseSettings, SettingsConfigDict
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


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

    @property
    def log_file(self) -> str:
        logs_file: str = str(Path(self.logs_path) / f"{self.service_name.lower()}.logs")
        return logs_file


settings = Settings()  # type: ignore


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

from sqlmodel import SQLModel, Field
from app.core.config import settings


class SettingBaseModel(SQLModel):
    http_proxy: str = Field(default=settings.http_proxy)
    soundcloud_oauth: str = Field(default=settings.soundcloud_oauth)
    concurrent_downloads: int = Field(default=settings.concurrent_downloads)
    concurrent_fragment_downloads: int = Field(
        default=settings.concurrent_fragment_downloads
    )
    download_folder: str = Field(default=settings.download_folder)
    download_retries: int = Field(default=settings.download_retries)


class SettingsModel(SettingBaseModel, table=True):
    id: int | None = Field(primary_key=True)


class SettingsPublicModel(SettingBaseModel):
    id: int


class SettingsCreateModel(SettingBaseModel): ...


class SettingsUpdateModel(SettingBaseModel): ...

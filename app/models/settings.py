from sqlmodel import SQLModel, Field
from app.core import config
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
    sync_interval: int = Field(default=settings.sync_interval)

    def get_http_headers(self) -> dict:
        headers = config.headers.copy()
        headers["authorization"] = self.soundcloud_oauth or settings.soundcloud_oauth
        return headers

    def get_http_cookies(self) -> dict:
        cookies = config.cookies.copy()
        cookies["oauth_token"] = self.soundcloud_oauth.lstrip(
            "OAuth "
        ) or settings.soundcloud_oauth.lstrip("OAuth ")
        return cookies

    def get_http_proxy(self) -> str | None:
        http_proxy = self.http_proxy or settings.http_proxy
        return http_proxy


class SettingsModel(SettingBaseModel, table=True):
    id: int | None = Field(primary_key=True)


class SettingsPublicModel(SettingBaseModel):
    id: int


class SettingsCreateModel(SettingBaseModel): ...


class SettingsUpdateModel(SettingBaseModel): ...

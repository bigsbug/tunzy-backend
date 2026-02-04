from app.core.logging import setup_logging
from app.soundcloud.auth import SoundCloudAuth
from aiohttp import ClientSession

logger = setup_logging(__name__)


async def get_playlists(
    session: ClientSession, sc_auth: SoundCloudAuth, limit: int = 100
):
    url = (
        "https://api-v2.soundcloud.com/me/library/all?"
        # "offset=2022-01-15T13%3A44%3A17.936Z"
        # "%2Csystem-playlist-like"
        # "%2C00000000000038985529"
        f"&limit={limit}"
        f"&client_id={sc_auth.client_id}"
        f"&app_version={sc_auth.app_version}"
        "&app_locale=en"
    )
    logger.info("Requesting url %s", url)
    playlists: list[dict] = []

    async with session.get(url) as req:
        content = await req.text()
        logger.info("User playlists api status %d length %d", req.status, len(content))
        if req.status != 200:
            logger.error(
                "Non-200 response from url %s content[2000]: %s", url, content[:2000]
            )
            return []
        data: dict = await req.json()
        collections: list[dict] = data.get("collection", {})
        for collection in collections:
            collection: dict
            playlist: dict = collection.get(
                "playlist",
                # fallback
                collection.get("system_playlist", {}),
            )
            playlists.append(playlist)

    logger.info("Extracted playlists total %d", len(playlists))
    return playlists


async def get_playlist_tracks() -> list[dict]: ...

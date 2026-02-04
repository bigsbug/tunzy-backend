from app.core.logging import setup_logging
from app.soundcloud.auth import SoundCloudAuth
from aiohttp import ClientSession
import re

logger = setup_logging(__name__)


async def get_playlists(
    session: ClientSession, sc_auth: SoundCloudAuth, limit: int = 100
) -> list[dict]:
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

async def get_liked_tracks(
    session: ClientSession, sc_auth: SoundCloudAuth, limit: int = 1000
) -> list[dict]:
    url = (
        f"https://api-v2.soundcloud.com/users/{sc_auth.user_id}/track_likes?"
        # "offset=2025-07-11T12%3A59%3A13.428Z%2Cuser-track-likes%2C000-00000000000751401199-00000000002038114156"
        f"&limit={limit}"
        f"&client_id={sc_auth.client_id}"
        f"&app_version={sc_auth.app_version}"
        "&app_locale=en"
    )
    logger.info("Requesting url %s ", url)
    liked_tracks: list[dict] = []
    while url:
        async with session.get(url) as req:
            content = await req.text()
            logger.info(
                "track likes Api response status %d length %d", req.status, len(content)
            )

            if req.status != 200:
                logger.error(
                    "Non-200 Response status %d content[2000]: %s",
                    req.status,
                    content[:2000],
                )
                return []

            data: dict = await req.json()
            tracks: list[dict] = data.get("collection", [])
            url: str | None = data.get("next_href")

            liked_tracks.extend(tracks)

            if url:
                logger.info("Paginate to next page %s", url)

    logger.info("Extracted liked tracks total %d", len(liked_tracks))

    return liked_tracks


async def get_playlist_tracks_ids(
    playlist_uri: str,
    session: ClientSession,
) -> list[str]:
    logger.info("request playlist page %s", playlist_uri)
    track_ids_regex = r'"id"\s*:\s*(\d+)\s*,\s*"kind"\s*:\s*"track"'

    async with session.get(playlist_uri) as req:
        content = await req.text()
        logger.info(
            "playlist page response status %d length %d", req.status, len(content)
        )
        if req.status != 200:
            logger.error(
                "Non-200 response status %d content[2000]: %s",
                req.status,
                content[:2000],
            )
            return []
        tracks_ids: list[str] = re.findall(track_ids_regex, content)
        logger.info("extracted playlist tracks IDs total %d", len(tracks_ids))
        logger.debug("extracted track ids : %s", tracks_ids)
    return tracks_ids


async def get_playlist_tracks(
    playlist_uri: str,
    session: ClientSession,
    sc_auth: SoundCloudAuth,
    batch_size_tracks_ids: int = 29,
) -> list[dict]:

    tracks_ids = await get_playlist_tracks_ids(playlist_uri, session)
    id_query_batch = []
    tracks_data: list[dict] = []

    for i in range(0, len(tracks_ids), batch_size_tracks_ids):
        ids_query = "%2C".join(tracks_ids[i : i + batch_size_tracks_ids])
        id_query_batch.append(ids_query)

    for ids_query in id_query_batch:
        url = (
            "https://api-v2.soundcloud.com/tracks?"
            f"ids={ids_query}"
            f"&client_id={sc_auth.client_id}"
            f"&app_version={sc_auth.app_version}"
            "&app_locale=en"
        )
        logger.info("requesting tracks api via url %s ", url)
        async with session.get(url) as req:
            content = await req.text()
            logger.info(
                "tracks api response status %d length %d", req.status, len(content)
            )
            if req.status != 200:
                logger.error(
                    "error on tracks api with status %d content[2000] %s",
                    req.status,
                    content[:2000],
                )
                return []
            tracks_data.extend(await req.json())

    logger.info("extracted tracks data total %d", len(tracks_data))

    return tracks_data
import asyncio
import aiohttp
from aiohttp import ClientSession
from app.core import config
from app.core.logging import setup_logging

import re
import dataclasses

logger = setup_logging(__name__)


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
    "authorization": config.settings.soundcloud_oauth,
}


@dataclasses.dataclass
class SoundCloudAuth:
    app_version: str
    client_id: str
    oauth: str = config.settings.soundcloud_oauth
    # third section of the OAuth is the user ID
    user_id: str = config.settings.soundcloud_oauth.split("-")[2]


async def get_client_id(session: ClientSession) -> str:

    home_page_url: str = "https://soundcloud.com/"
    regex_client_id: str = r'"id"\s*:\s*"([^"]+)"'
    timeout = aiohttp.ClientTimeout(10)
    logger.info("request to %s with timeout=%d", home_page_url, timeout.total)
    try:
        async with session.get(
            home_page_url,
            timeout=timeout,
        ) as req:
            html = await req.text()
            logger.info("Homepage status %d length %d", req.status, len(html))

            if req.status != 200:
                logger.error("non-200 status html[2000]:%s", html[:2000])
                return ""

            logger.info("search for client ID on homepage")
            target_math = re.search(
                regex_client_id,
                html,
            )
            if target_math:
                client_id: str = target_math.group(1)
                logger.info("Client ID matched : %s", client_id)
            else:
                client_id = ""
                logger.warning("Client ID matched : %s", "NotFound")

            return client_id
    except asyncio.TimeoutError:
        logger.error("Timeout HomePage After %d", timeout.total)
    except Exception as error:
        logger.error("unknown Error on requesting homepage: %s", error)
    return ""


async def get_app_version(session: ClientSession) -> str:
    url: str = "https://soundcloud.com/versions.json"
    logger.info("requesting %s", url)
    async with session.get(url, headers=headers) as req:
        html = await req.text()
        json = await req.json()
        logger.info("Versions Page status %d length %d", req.status, len(html))
        version = json.get("app")
        logger.info("App Version is %s", version or "NotFound")
        if not version:
            logger.error("Version NotFound data: %s", html)

    return version


async def get_track_authorization() -> str: ...

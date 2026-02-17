import aiohttp
from fastapi import APIRouter, Path, HTTPException, Request, status
from typing import Annotated
from app.core import config
from app.core.db import SessionDep
from app.core.logging import get_logger
from app.models.playlist import (
    PlaylistModel,
    PlaylistPublicModel,
    TrackModel,
    TrackPublicModel,
)
from app.models.settings import SettingsModel
from app.schemas.playlist import PlaylistSchema
from app.soundcloud.auth import SoundCloudAuth, get_app_version, get_client_id
from app.soundcloud.playlist import get_playlist, get_playlists, get_playlist_tracks
from urllib.parse import unquote
from sqlmodel import select, exists, update, or_

router = APIRouter(prefix="/playlists")
logger = get_logger(__name__)


@router.get("/", response_model=list[PlaylistPublicModel])
async def playlists(orm: SessionDep):
    statement = select(PlaylistModel)
    items = orm.exec(statement).fetchall()
    return items


@router.get("/{id:int}/", response_model=PlaylistPublicModel)
async def playlist(id: Annotated[int, Path(title="ID of playlist")], orm: SessionDep):
    playlist_statement = select(PlaylistModel).where(PlaylistModel.id == id)
    playlist_obj = orm.exec(playlist_statement).one_or_none()
    if not playlist_obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Playlist Not Found")
    return playlist_obj


@router.get("/{id:int}/tracks/", response_model=list[TrackPublicModel])
async def tracks(
    id: Annotated[int, Path(title="ID of playlist")], orm: SessionDep, request: Request
):
    tracks_statement = select(TrackModel).where(TrackModel.playlists.any(id=id))  # type: ignore
    tracks = orm.exec(tracks_statement).fetchall()
    return [track.to_public_model(request) for track in tracks]


@router.post("/sync/")
async def sync_playlists(orm: SessionDep):

    settings_query = select(SettingsModel)
    settings = orm.exec(settings_query).one_or_none()
    http_proxy = settings.http_proxy if settings else config.settings.http_proxy
    async with aiohttp.ClientSession(
        proxy=http_proxy,
        headers=config.headers,
    ) as session:
        client_id = await get_client_id(session)
        app_version = await get_app_version(session)
        sc_auth = SoundCloudAuth(client_id, app_version)
        res = await get_playlists(session, sc_auth)

    items_id = [obj.platform_id for obj in res]
    logger.info("palylists ids: %s", items_id)

    search_query = (
        select(PlaylistModel)
        .where(PlaylistModel.service == "soundcloud")
        .where(PlaylistModel.platform_id.in_(items_id))  # type: ignore
    )
    search_result = orm.exec(search_query).fetchall()

    lookup_objs = {obj.platform_id: obj for obj in search_result}
    updated_items = []
    created_items = []

    for obj in res:
        item = lookup_objs.get(str(obj.platform_id))
        if item:
            item.update_from_schema(obj)
            updated_items.append(item)
        else:
            new_item = PlaylistModel.from_schema(obj)
            new_item.service = "soundcloud"
            orm.add(new_item)
            created_items.append(new_item)

    orm.commit()

    return {
        "updated_playlists": len(updated_items),
        "created_playlists": len(created_items),
        "total": len(res),
    }


@router.post("/{id}/sync/")
async def sync_playlist_tracks(
    id: Annotated[int, Path(title="ID or playlist")], orm: SessionDep
):
    playlist_obj_statement = select(PlaylistModel).where(PlaylistModel.id == id)
    playlist_obj = orm.exec(playlist_obj_statement).one_or_none()
    if not playlist_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist Not Found"
        )
    if not playlist_obj.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This Playlist Is Offline"
        )
    settings_query = select(SettingsModel)
    settings = orm.exec(settings_query).one_or_none()
    http_proxy = settings.http_proxy if settings else config.settings.http_proxy

    async with aiohttp.ClientSession(
        proxy=http_proxy,
        headers=config.headers,
    ) as session:
        client_id = await get_client_id(session)
        app_version = await get_app_version(session)
        sc_auth = SoundCloudAuth(client_id, app_version)
        res = await get_playlist_tracks(playlist_obj.url, session, sc_auth)

    created_tracks = []
    updated_tracks = []

    tracks_ids = {obj.platform_id for obj in res}

    tracks_statement = select(TrackModel).where(
        or_(TrackModel.playlists.any(id=id), TrackModel.platform_id.in_(tracks_ids))  # type: ignore
    )
    tracks = orm.exec(tracks_statement).fetchall()

    tracks_objs_lookup_ids = {obj.platform_id: obj for obj in tracks}
    for obj in res:
        item = tracks_objs_lookup_ids.get(obj.platform_id)

        if item and item.platform_id not in tracks_ids:
            item.playlists.remove(playlist_obj)
            updated_tracks.append(item)
        elif item and playlist_obj in item.playlists:
            continue
        elif item and playlist_obj not in item.playlists:
            item.playlists.append(playlist_obj)
            updated_tracks.append(item)
        else:
            new_item = TrackModel.from_schema(obj)
            new_item.playlists = [playlist_obj]
            orm.add(new_item)
            created_tracks.append(new_item)

    orm.commit()

    return {
        "created_tracks": len(created_tracks),
        "updated_tracks": len(updated_tracks),
        "unchanged_tracks": len(tracks) - (len(created_tracks) + len(updated_tracks)),
        "total": len(tracks),
    }

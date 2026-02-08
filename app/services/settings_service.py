from fastapi import HTTPException, status
from fastapi.routing import APIRouter
from sqlmodel import select
from app.core.db import SessionDep
from app.models.settings import (
    SettingsModel,
    SettingsPublicModel,
    SettingsUpdateModel,
)

router = APIRouter(prefix="/settings")


@router.get("/", response_model=SettingsPublicModel)
async def get_settings(orm: SessionDep):
    query = select(SettingsModel)
    setting = orm.exec(query).one_or_none()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return setting


@router.patch("/", response_model=SettingsPublicModel)
async def update_settings(settings_data: SettingsUpdateModel, orm: SessionDep):
    validated_settings_data = SettingsUpdateModel.model_validate(settings_data)
    query = select(SettingsModel)
    setting = orm.exec(query).one_or_none()
    if not setting:
        setting = SettingsModel(**validated_settings_data.model_dump())
        orm.add(setting)
    else:
        setting.sqlmodel_update(validated_settings_data.model_dump())
        orm.add(setting)
    orm.commit()
    return setting

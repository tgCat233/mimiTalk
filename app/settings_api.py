"""设置接口（S1 设置页）。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import characters, settings
from app.config import HISTORY_LIMIT_MAX

router = APIRouter(prefix="/api")


class ModelSettings(BaseModel):
    base_url: str = ""
    api_key: str | None = None
    model: str = ""
    fake: bool = False
    history_limit: int = Field(default=30, ge=1, le=HISTORY_LIMIT_MAX)


class TTSSettings(BaseModel):
    provider: str = "openai-compatible"
    base_url: str = ""
    api_key: str | None = None
    model: str = ""
    voice: str = ""
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    mode: Literal["text", "voice"] = "text"


class SettingsUpdate(BaseModel):
    model: ModelSettings | None = None
    tts: TTSSettings | None = None


class TTSCharacterModel(BaseModel):
    character_id: str = Field(min_length=1)
    model: str = ""


@router.get("/settings")
def get_settings() -> dict:
    return settings.public_settings()


@router.put("/settings")
def put_settings(payload: SettingsUpdate) -> dict:
    data = payload.model_dump(exclude_none=True)
    return settings.update_settings(data)


@router.put("/tts/characters")
def put_tts_character(payload: TTSCharacterModel) -> dict:
    """单独保存某角色的语音模型；空模型 = 取消该角色映射。"""
    if characters.get_character(payload.character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return settings.update_settings(
        {"tts": {"character_models": {payload.character_id: payload.model}}}
    )

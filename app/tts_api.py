"""TTS 接口（S2）：状态、音色列表、分句、试听与逐句合成。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app import db, tts
from app.config import load_config

router = APIRouter(prefix="/api")


_locks: dict[str, asyncio.Lock] = {}
_semaphore = asyncio.Semaphore(2)


class SynthesizeIn(BaseModel):
    message_id: str
    text: str
    index: int = Field(default=0, ge=0, le=500)


class PreviewIn(BaseModel):
    text: str = "你好，我是薇儿丹蒂，今天也一起加油吧。"
    character_id: str | None = None
    model: str | None = None


def _mapped_model(cfg: dict, character_id: str | None) -> str:
    mapping = cfg.get("character_models") or {}
    return str(mapping.get(str(character_id or "")) or "").strip()


def _character_voice(cfg: dict, character_id: str | None) -> tuple[str, str]:
    """聊天合成只认角色映射，避免串用其他角色的音色。"""
    model = _mapped_model(cfg, character_id)
    if not model:
        raise tts.TTSError("该角色未配置语音模型")
    return model, ""


def _preview_voice(
    cfg: dict, character_id: str | None, model_override: str | None
) -> tuple[str, str]:
    override = str(model_override or "").strip()
    if override:
        return override, ""
    mapped = _mapped_model(cfg, character_id)
    if mapped:
        return mapped, ""
    default = str(cfg.get("model") or "").strip()
    if default:
        return default, str(cfg.get("voice") or "")
    raise tts.TTSError("未配置语音模型")


@router.get("/tts/status")
async def tts_status() -> dict:
    config = load_config()
    cfg = config.get("tts", {})
    status = tts.public_status(config)
    if not status["configured"]:
        status.update({"reachable": False, "detail": "未配置 TTS 接口地址"})
        return status
    try:
        status.update(await tts.fetch_health(cfg))
    except tts.TTSError as exc:
        status.update({"reachable": False, "detail": str(exc)})
    return status


@router.get("/tts/models")
async def tts_models() -> dict:
    config = load_config()
    cfg = config.get("tts", {})
    if not tts.is_configured(cfg):
        raise HTTPException(status_code=400, detail="未配置 TTS 接口地址")
    try:
        return await tts.fetch_models(cfg)
    except tts.TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tts/preview")
async def tts_preview(payload: PreviewIn) -> Response:
    config = load_config()
    cfg = config.get("tts", {})
    if not tts.is_configured(cfg):
        raise HTTPException(status_code=400, detail="未配置 TTS 接口地址")
    text = (payload.text or "").strip()[:200]
    try:
        model, voice = _preview_voice(cfg, payload.character_id, payload.model)
    except tts.TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        async with _semaphore:
            audio = await tts.synthesize(text, cfg, model=model, voice=voice)
    except tts.TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/wav")


@router.post("/tts/synthesize")
async def tts_synthesize(payload: SynthesizeIn) -> dict:
    config = load_config()
    cfg = config.get("tts", {})
    if not tts.is_configured(cfg):
        raise HTTPException(status_code=400, detail="未配置 TTS 接口地址")

    with db.session() as conn:
        message = db.get_message(conn, payload.message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="消息不存在")
        conversation = db.get_conversation(conn, message["conversation_id"])
        character_id = conversation.get("contact_id") if conversation else None

    try:
        model, voice = _character_voice(cfg, character_id)
    except tts.TTSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    text = (payload.text or "").strip()
    try:
        async with _semaphore:
            audio = await tts.synthesize(text, cfg, model=model, voice=voice)
        clip = tts.save_clip(
            payload.message_id,
            payload.index,
            audio,
            cfg,
            text,
            model=model,
            voice=voice,
        )
    except tts.TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    lock = _locks.setdefault(payload.message_id, asyncio.Lock())
    async with lock:
        with db.session() as conn:
            current = db.get_message(conn, payload.message_id)
            if current is None:
                raise HTTPException(status_code=404, detail="消息不存在")
            meta = current.get("meta") or {}
            voice_meta = meta.get("voice") or {}
            clips = [
                item
                for item in (voice_meta.get("clips") or [])
                if item.get("index") != clip["index"]
            ]
            clips.append(clip)
            clips.sort(key=lambda item: item.get("index", 0))
            voice_meta.update(
                {
                    "provider": str(cfg.get("provider") or "openai-compatible"),
                    "model": model,
                    "voice": voice,
                    "speed": tts.speed_of(cfg),
                    "clips": clips,
                    "error": "",
                }
            )
            meta["voice"] = voice_meta
            message = db.update_message(
                conn, payload.message_id, type="voice", meta=meta
            )
    return {"message": message, "clip": clip}


@router.get("/tts/audio/{message_id}/{filename}")
def tts_audio(message_id: str, filename: str) -> FileResponse:
    try:
        path = tts.clip_path(message_id, filename)
    except tts.TTSError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/wav")

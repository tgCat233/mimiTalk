"""外部 TTS API 接入（S2）。

只对接用户已就绪的 OpenAI 兼容语音服务：本模块不做本地部署、权重微调，
也不提供替代 TTS 实现；测试在 HTTP 层打桩。
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import shutil
import time
import wave
from pathlib import Path

import httpx

from app.config import BASE_DIR

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
MAX_TEXT = 2000
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class TTSError(RuntimeError):
    pass


def tts_dir() -> Path:
    """音频目录：环境变量 > 默认 data/tts。"""
    env = os.environ.get("P3_TTS_DIR")
    return Path(env) if env else BASE_DIR / "data" / "tts"


def is_configured(cfg: dict) -> bool:
    return bool(str(cfg.get("base_url") or "").strip())


def _base(cfg: dict) -> str:
    base = str(cfg.get("base_url") or "").strip().rstrip("/")
    if not base:
        raise TTSError("未配置 TTS 接口地址")
    return base


def _headers(cfg: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    key = str(cfg.get("api_key") or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def speed_of(cfg: dict) -> float:
    try:
        return float(cfg.get("speed") or 1.0)
    except (TypeError, ValueError):
        return 1.0


def public_status(config: dict) -> dict:
    cfg = config.get("tts", {})
    return {
        "configured": is_configured(cfg),
        "base_url": str(cfg.get("base_url") or ""),
        "has_key": bool(str(cfg.get("api_key") or "").strip()),
        "model": str(cfg.get("model") or ""),
        "voice": str(cfg.get("voice") or ""),
        "speed": speed_of(cfg),
        "mode": str(cfg.get("mode") or "text"),
        "character_models": {
            str(key): str(value)
            for key, value in (cfg.get("character_models") or {}).items()
        },
    }


def _voice_id(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("id", "name", "voice", "speaker"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def normalize_models(payload) -> dict:
    """把不同形态的 /v1/models 响应归一为 {models:[{id,voices}], voices:[]}。"""
    models: dict[str, list[str]] = {}
    loose: list[str] = []

    def add_model(model_id, voices=None) -> None:
        mid = str(model_id or "").strip()
        if not mid:
            return
        bucket = models.setdefault(mid, [])
        for item in voices if isinstance(voices, list) else []:
            vid = _voice_id(item)
            if vid and vid not in bucket:
                bucket.append(vid)

    def add_voice(item) -> None:
        vid = _voice_id(item)
        if vid and vid not in loose:
            loose.append(vid)

    def walk(items) -> None:
        for item in items:
            if isinstance(item, str):
                add_model(item)
                continue
            if not isinstance(item, dict):
                continue
            model_id = item.get("id") or item.get("model") or item.get("name")
            voices = item.get("voices")
            if voices is None and item.get("voice") is not None:
                voices = [item["voice"]]
            if voices is None and item.get("speakers") is not None:
                voices = item["speakers"]
            if model_id:
                add_model(model_id, voices)
            elif isinstance(voices, list):
                for value in voices:
                    add_voice(value)
            else:
                add_voice(item)

    if isinstance(payload, list):
        walk(payload)
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            walk(payload["data"])
        elif isinstance(payload.get("models"), list):
            walk(payload["models"])
        elif isinstance(payload.get("voices"), list):
            for item in payload["voices"]:
                add_voice(item)
        else:
            for key, value in payload.items():
                if isinstance(value, list):
                    add_model(key, value)

    voices: list[str] = []
    for values in models.values():
        for value in values:
            if value not in voices:
                voices.append(value)
    for value in loose:
        if value not in voices:
            voices.append(value)
    return {
        "models": [{"id": key, "voices": values} for key, values in models.items()],
        "voices": voices,
    }


async def fetch_models(cfg: dict) -> dict:
    """读取 API 提供的模型 / 音色列表。"""
    base = _base(cfg)
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.get(f"{base}/models", headers=_headers(cfg))
    except httpx.HTTPError as exc:
        raise TTSError(f"TTS 接口连接失败：{exc}") from exc
    if response.status_code >= 400:
        body = response.text[:300]
        raise TTSError(f"TTS 接口返回 {response.status_code}：{body}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise TTSError("TTS 模型列表不是合法 JSON") from exc
    result = normalize_models(payload)
    result["count"] = len(result["models"]) + len(result["voices"])
    return result


async def fetch_health(cfg: dict) -> dict:
    """探测服务是否可达；无 /health 时退回 /models。"""
    base = _base(cfg)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(8.0, connect=4.0)) as client:
            response = await client.get(f"{base}/health", headers=_headers(cfg))
    except httpx.HTTPError as exc:
        raise TTSError(f"TTS 接口连接失败：{exc}") from exc
    latency = round((time.perf_counter() - started) * 1000)
    if response.status_code >= 400:
        await fetch_models(cfg)
    return {"reachable": True, "latency_ms": latency}


async def synthesize(
    text: str,
    cfg: dict,
    *,
    model: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
) -> bytes:
    """调用 /v1/audio/speech，返回 WAV 字节。"""
    text = (text or "").strip()
    if not text:
        raise TTSError("合成文本为空")
    if len(text) > MAX_TEXT:
        raise TTSError("合成文本过长")

    payload: dict = {"input": text}
    model_name = str(model if model is not None else cfg.get("model") or "").strip()
    voice_name = str(voice if voice is not None else cfg.get("voice") or "").strip()
    if model_name:
        payload["model"] = model_name
    if voice_name:
        payload["voice"] = voice_name
    speed_value = speed_of(cfg) if speed is None else float(speed)
    payload["speed"] = max(0.5, min(2.0, speed_value))

    response = None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{_base(cfg)}/audio/speech", headers=_headers(cfg), json=payload
                )
            break
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(0.4)
    if response is None:
        raise TTSError(f"TTS 接口连接失败：{last_error}") from last_error
    if response.status_code >= 400:
        body = response.text[:300]
        raise TTSError(f"TTS 接口返回 {response.status_code}：{body}")

    data = response.content
    if not data:
        raise TTSError("TTS 返回空音频")
    if len(data) > MAX_AUDIO_BYTES:
        raise TTSError("TTS 返回音频过大")
    if not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        raise TTSError("TTS 返回的不是 WAV 音频")
    return data


def wav_duration(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
            return round(frames / rate, 2) if rate else 0.0
    except (wave.Error, EOFError):
        return 0.0


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", value or "")


def clip_key(cfg: dict, text: str, model: str, voice: str, speed: float) -> str:
    raw = "|".join(
        [
            str(cfg.get("provider") or ""),
            str(cfg.get("base_url") or ""),
            model,
            voice,
            str(speed),
            text,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def save_clip(
    message_id: str,
    index: int,
    data: bytes,
    cfg: dict,
    text: str,
    *,
    model: str | None = None,
    voice: str | None = None,
) -> dict:
    """落盘单句音频，返回前端可用的 clip 元数据。"""
    mid = _safe_id(message_id)
    if not mid:
        raise TTSError("消息 ID 非法")
    directory = tts_dir() / mid
    directory.mkdir(parents=True, exist_ok=True)

    model_name = str(model if model is not None else cfg.get("model") or "")
    voice_name = str(voice if voice is not None else cfg.get("voice") or "")
    digest = clip_key(cfg, text, model_name, voice_name, speed_of(cfg))
    filename = f"{max(0, index):03d}-{digest[:8]}.wav"
    target = directory / filename
    cached = target.is_file()
    if not cached:
        target.write_bytes(data)
    return {
        "index": index,
        "url": f"/api/tts/audio/{mid}/{filename}",
        "duration": wav_duration(data),
        "cached": cached,
    }


def clip_path(message_id: str, filename: str) -> Path:
    mid = _safe_id(message_id)
    name = re.sub(r"[^A-Za-z0-9_.-]", "", filename or "")
    if not mid or not name.endswith(".wav"):
        raise TTSError("音频路径非法")
    root = tts_dir().resolve()
    target = (root / mid / name).resolve()
    if target.parent.parent != root or not target.is_file():
        raise TTSError("音频不存在")
    return target


def cleanup_message(message_id: str) -> None:
    mid = _safe_id(message_id)
    if not mid:
        return
    shutil.rmtree(tts_dir() / mid, ignore_errors=True)

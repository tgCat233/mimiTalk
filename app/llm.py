"""OpenAI 兼容模型接入（S1-D-1）。"""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import AsyncIterator

import httpx

try:
    import truststore


    _SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except Exception:
    _SSL_CONTEXT = None

FAKE_REPLY = "（示例回复）我在听，你继续说。"


class LLMError(RuntimeError):
    pass


def _has_key(cfg: dict) -> bool:
    return bool(str(cfg.get("api_key") or "").strip())


def is_fake(cfg: dict) -> bool:
    """未填 API Key 时自动回退示例回复；否则按显式 fake 开关。"""
    return bool(cfg.get("fake")) or not _has_key(cfg)


def model_status(config: dict) -> dict:
    """返回可公开的模型配置状态（不含密钥）。"""
    cfg = config.get("model", {})
    fake = is_fake(cfg)
    ai_ready = _has_key(cfg) and bool(cfg.get("base_url")) and bool(cfg.get("model"))
    return {
        "configured": ai_ready or fake,
        "fake": fake,
        "ai_ready": ai_ready,
        "has_key": _has_key(cfg),
        "model": str(cfg.get("model") or ""),
        "base_url": str(cfg.get("base_url") or ""),
    }


async def stream_chat(messages: list[dict], config: dict) -> AsyncIterator[str]:
    """按 OpenAI 兼容协议流式产出文本增量。"""
    cfg = config.get("model", {})

    if is_fake(cfg):
        for char in FAKE_REPLY:
            await asyncio.sleep(0.03)
            yield char
        return

    base_url = str(cfg.get("base_url") or "").rstrip("/")
    model = str(cfg.get("model") or "")
    if not base_url or not model:
        raise LLMError("未配置模型：请在 config/p3.toml 填写 [model] 的 base_url 与 model")

    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    payload = {"model": model, "messages": messages, "stream": True}

    try:
        async with httpx.AsyncClient(timeout=None, verify=_SSL_CONTEXT) as client:
            async with client.stream(
                "POST", f"{base_url}/chat/completions", headers=headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")[:500]
                    raise LLMError(f"模型接口返回 {response.status_code}：{body}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload_obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = payload_obj.get("choices") or []
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content")
                    if content:
                        yield content
    except httpx.HTTPError as exc:
        raise LLMError(f"模型接口连接失败：{exc}") from exc

"""对话流式接口（S1-D-1）。"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import db, llm
from app.config import HISTORY_LIMIT_MAX, load_config
from app.personas import load_persona
from app.texts import load_texts

router = APIRouter(prefix="/api")

DEFAULT_SYSTEM_PROMPT = "你是 P3 的聊天角色，请用简短、自然的中文回复。"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_model_messages(
    history: list[dict], system_prompt: str, recall_notice: str | None = None
) -> list[dict]:
    """把持久化历史转换成模型输入；引用的原文以用户消息前缀注入。"""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for item in history:
        if item["type"] not in ("text", "voice") or not item.get("content"):
            continue
        role = item["role"] if item["role"] in ("user", "assistant", "system") else "user"
        content = str(item.get("content") or "")
        quote = (item.get("meta") or {}).get("quote")
        if role == "user" and isinstance(quote, dict):
            if quote.get("deleted"):
                prefix = "[引用：原消息已删除]"
            else:
                name = str(quote.get("name") or "")
                text = str(quote.get("text") or "")
                prefix = f"[引用 {name}：{text}]" if text else "[引用]"
            content = f"{prefix}\n{content}"
        messages.append({"role": role, "content": content})
    if recall_notice:
        messages.append({"role": "user", "content": recall_notice})
    return messages


@router.get("/model")
def model_status() -> dict:
    """返回当前模型配置状态（不含密钥）。"""
    return llm.model_status(load_config())


@router.post("/conversations/{conversation_id}/chat/stream")
async def chat_stream(
    conversation_id: str, recall_notice: bool = False
) -> StreamingResponse:
    """基于当前会话历史生成回复，以 SSE 流式返回。"""
    config = load_config()
    with db.session() as conn:
        conversation = db.get_conversation(conn, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if conversation.get("kind") == "group":
            raise HTTPException(status_code=400, detail="群聊回复尚未接入")
        history = db.list_messages(
            conn,
            conversation_id,
            limit=int(config["model"].get("history_limit", 30)),
            max_limit=HISTORY_LIMIT_MAX,
        )

    persona = load_persona(conversation.get("contact_id"), conversation.get("title"))
    system_prompt = (
        persona["system_prompt"] if persona else DEFAULT_SYSTEM_PROMPT
    )
    notice = None
    if recall_notice:
        notice_text = load_texts().get("recall_notice", "管理员撤回了一条消息")
        notice = f"<{notice_text}>"
    messages = build_model_messages(history, system_prompt, notice)

    if len(messages) == 1:
        raise HTTPException(status_code=400, detail="没有可回复的文本消息")

    async def generate() -> AsyncIterator[str]:
        collected: list[str] = []
        try:
            yield _sse("start", {"conversation_id": conversation_id})
            async for delta in llm.stream_chat(messages, config):
                collected.append(delta)
                yield _sse("delta", {"text": delta})
            with db.session() as conn:
                message = db.add_message(
                    conn,
                    conversation_id,
                    role="assistant",
                    type="text",
                    content="".join(collected),
                )
            yield _sse("end", {"message": message})
        except llm.LLMError as exc:
            yield _sse("error", {"detail": str(exc)})
        except Exception as exc:
            yield _sse("error", {"detail": f"生成失败：{exc}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

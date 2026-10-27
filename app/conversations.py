"""会话与消息接口（S1-B-1）。"""

from __future__ import annotations

import random
import time
from sqlite3 import IntegrityError
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import characters, db, favorites, tts
from app.config import load_config
from app.personas import load_persona, save_persona
from app.texts import load_texts

router = APIRouter(prefix="/api")


class ConversationCreate(BaseModel):
    character_id: str = Field(min_length=1)


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    type: Literal["text", "image", "sticker", "voice", "system", "recall"] = "text"
    content: str | None = None
    asset_id: str | None = None
    file_id: str | None = None
    width: int | None = None
    height: int | None = None
    reply_to_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


RECALL_WINDOW_MS = 120_000


def _quote_snippet(message: dict) -> str:
    if message["type"] == "image":
        return "[图片]"
    if message["type"] == "sticker":
        return "[表情]"
    if message["type"] == "voice":
        return "[语音]"
    return message.get("content") or ""


def _quote_name(message: dict, conversation: dict) -> str:
    if message["role"] == "user":
        return "管理员"
    return str(conversation.get("title") or "角色")


@router.get("/conversations")
def list_conversations() -> list[dict]:
    with db.session() as conn:
        return db.list_conversations(conn)


@router.get("/characters")
def list_characters() -> list[dict]:
    """全部可会话联系人（单聊角色 + 官方群）；带回会话 id 与收藏状态。"""
    with db.session() as conn:
        conversations = db.list_conversations(conn)
    by_contact = {
        item["contact_id"]: item["id"]
        for item in conversations
        if item.get("contact_id")
    }
    favorite_ids = favorites.favorite_ids()
    return [
        {
            **contact,
            "conversation_id": by_contact.get(contact["id"]),
            "favorite": contact["id"] in favorite_ids,
        }
        for contact in characters.CONTACTS
    ]


class FavoriteUpdate(BaseModel):
    favorite: bool


@router.put("/characters/{character_id}/favorite")
def update_favorite(character_id: str, payload: FavoriteUpdate) -> dict:
    """切换联系人收藏；只影响新建列表排序，不创建会话。"""
    contact = characters.get_contact(character_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    favorites.set_favorite(contact["id"], payload.favorite)
    return {"id": contact["id"], "favorite": payload.favorite}


@router.get("/personas")
def list_personas() -> dict[str, str]:
    """全部单聊角色的系统提示词（缺失时返回占位提示词）。"""
    return {
        character["id"]: (load_persona(character["id"], character["name"]) or {}).get(
            "system_prompt", ""
        )
        for character in characters.HEROES
    }


class PersonaUpdate(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=8000)


@router.get("/characters/{character_id}/persona")
def get_persona(character_id: str) -> dict:
    """查看角色卡（本地调试用）；无专属角色卡时返回占位提示词。"""
    character = characters.get_character(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色卡不存在")
    persona = load_persona(character_id, character["name"])
    if persona is None:
        raise HTTPException(status_code=404, detail="角色卡不存在")
    return persona


@router.put("/characters/{character_id}/persona")
def update_persona(character_id: str, payload: PersonaUpdate) -> dict:
    character = characters.get_character(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="未支持的角色")
    return save_persona(character["id"], character["name"], payload.system_prompt)


@router.post("/conversations", status_code=201)
def create_conversation(payload: ConversationCreate) -> dict:
    contact = characters.get_contact(payload.character_id)
    if contact is None:
        raise HTTPException(status_code=400, detail="未支持的角色")

    with db.session() as conn:
        if db.get_conversation_by_contact(conn, contact["id"]) is not None:
            raise HTTPException(status_code=409, detail="该联系人已有会话")
        try:
            return db.create_conversation(
                conn,
                title=contact["name"],
                kind=contact["kind"],
                contact_id=contact["id"],
            )
        except IntegrityError:
            raise HTTPException(status_code=409, detail="该联系人已有会话") from None


class ConversationSettingsUpdate(BaseModel):
    admin_avatar: str | None = None
    bubble_theme: str | None = None


@router.put("/conversations/{conversation_id}/settings")
def update_conversation_settings(
    conversation_id: str, payload: ConversationSettingsUpdate
) -> dict:
    with db.session() as conn:
        conversation = db.get_conversation(conn, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        settings = dict(conversation.get("settings") or {})
        settings.update(payload.model_dump(exclude_none=True))
        return db.update_conversation_settings(conn, conversation_id, settings)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str) -> None:
    with db.session() as conn:
        message_ids = db.list_message_ids(conn, conversation_id)
        if not db.delete_conversation(conn, conversation_id):
            raise HTTPException(status_code=404, detail="会话不存在")
    for message_id in message_ids:
        tts.cleanup_message(message_id)


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, limit: int = 50) -> list[dict]:
    with db.session() as conn:
        if db.get_conversation(conn, conversation_id) is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return db.list_messages(conn, conversation_id, limit=limit)


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def create_message(conversation_id: str, payload: MessageCreate) -> dict:
    with db.session() as conn:
        conversation = db.get_conversation(conn, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        meta = dict(payload.meta or {})
        if payload.reply_to_id:
            target = db.get_message(conn, payload.reply_to_id)
            if target is None or target["conversation_id"] != conversation_id:
                raise HTTPException(status_code=400, detail="被引用的消息不存在")
            if target["type"] in ("recall", "system"):
                raise HTTPException(status_code=400, detail="该消息不能引用")
            meta["quote"] = {
                "id": target["id"],
                "role": target["role"],
                "name": _quote_name(target, conversation),
                "type": target["type"],
                "text": _quote_snippet(target),
            }
        return db.add_message(
            conn,
            conversation_id,
            role=payload.role,
            type=payload.type,
            content=payload.content,
            asset_id=payload.asset_id,
            file_id=payload.file_id,
            width=payload.width,
            height=payload.height,
            reply_to_id=payload.reply_to_id,
            meta=meta,
        )


@router.delete("/conversations/{conversation_id}/messages/{message_id}", status_code=204)
def delete_message(conversation_id: str, message_id: str) -> None:
    with db.session() as conn:
        message = db.get_message(conn, message_id)
        if message is None or message["conversation_id"] != conversation_id:
            raise HTTPException(status_code=404, detail="消息不存在")
        db.delete_message(conn, conversation_id, message_id)
        db.mark_quote_deleted(conn, conversation_id, message_id)
    tts.cleanup_message(message_id)


@router.post("/conversations/{conversation_id}/messages/{message_id}/recall")
def recall_message(conversation_id: str, message_id: str) -> dict:
    config = load_config()
    with db.session() as conn:
        conversation = db.get_conversation(conn, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        message = db.get_message(conn, message_id)
        if message is None or message["conversation_id"] != conversation_id:
            raise HTTPException(status_code=404, detail="消息不存在")
        if message["role"] != "user":
            raise HTTPException(status_code=400, detail="只能撤回自己发送的消息")
        if int(time.time() * 1000) - int(message["created_at"]) > RECALL_WINDOW_MS:
            raise HTTPException(status_code=400, detail="超过两分钟，无法撤回")
        db.delete_message(conn, conversation_id, message_id)
        db.mark_quote_deleted(conn, conversation_id, message_id)
        notice_text = load_texts().get("recall_notice", "管理员撤回了一条消息")
        notice = db.add_message(
            conn,
            conversation_id,
            role="system",
            type="recall",
            content=f"<{notice_text}>",
            meta={"display_text": notice_text, "recall_of": message_id},
        )
        try:
            chance = float(config.get("chat", {}).get("recall_reply_chance", 0.3))
        except (TypeError, ValueError):
            chance = 0.3
        chance = max(0.0, min(1.0, chance))
        will_reply = conversation.get("kind") != "group" and random.random() < chance
    tts.cleanup_message(message_id)
    return {"message": notice, "will_reply": will_reply}

"""可会话联系人：单聊角色与官方群（数据源：头像索引 avatars.json）。"""

from __future__ import annotations

import json

from app.config import BASE_DIR

AVATARS_PATH = BASE_DIR / "app" / "static" / "assets" / "avatars" / "avatars.json"


INITIAL_CONTACT_IDS = ("1084", "1085", "1039")
TTS_CHARACTER_IDS = frozenset(INITIAL_CONTACT_IDS)


def _load_contacts() -> tuple[list[dict], dict[str, dict]]:
    data = json.loads(AVATARS_PATH.read_text(encoding="utf-8"))
    contacts: list[dict] = []
    for name, item in data.get("heroes", {}).items():
        contacts.append(
            {
                "id": str(item["id"]),
                "name": name,
                "avatar": item.get("url") or "",
                "kind": "single",
            }
        )
    for name, item in data.get("groups", {}).items():
        contacts.append(
            {
                "id": str(item["id"]),
                "name": name,
                "avatar": item.get("url") or "",
                "kind": "group",
            }
        )
    for contact in contacts:
        contact["tts"] = contact["id"] in TTS_CHARACTER_IDS
        contact["tts_rank"] = (
            INITIAL_CONTACT_IDS.index(contact["id"])
            if contact["id"] in TTS_CHARACTER_IDS
            else -1
        )
    return contacts, {contact["id"]: contact for contact in contacts}


CONTACTS, _BY_ID = _load_contacts()
HEROES = [contact for contact in CONTACTS if contact["kind"] == "single"]


def get_contact(contact_id: str | None) -> dict | None:
    """按 id 取联系人；群聊与单聊角色都可命中。"""
    if contact_id is None or contact_id == "":
        return None
    return _BY_ID.get(str(contact_id))


def get_character(character_id: str | None) -> dict | None:
    """按 id 取单聊角色；群聊不算角色。"""
    contact = get_contact(character_id)
    return contact if contact and contact["kind"] == "single" else None


def initial_contacts() -> list[dict]:
    """首次启动需要预建的会话联系人。"""
    return [contact for contact in (get_character(cid) for cid in INITIAL_CONTACT_IDS) if contact]

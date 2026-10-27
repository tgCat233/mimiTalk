"""角色卡加载（S1-E-1）。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app import characters
from app.config import BASE_DIR

PERSONA_DIR = BASE_DIR / "config" / "personas"
DEFAULT_PERSONA_FILE = "_default.persona.json"


def persona_dir() -> Path:
    env = os.environ.get("P3_PERSONA_DIR")
    return Path(env) if env else PERSONA_DIR


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _default_template() -> str:
    data = _read_json(persona_dir() / DEFAULT_PERSONA_FILE)
    if not data:
        return ""
    return str(data.get("system_prompt") or "").strip()


def load_persona(character_id: str | None, name: str | None = None) -> dict | None:
    """按角色 id 读取角色卡；没有专属角色卡时回退到一句占位提示词。"""
    if not character_id:
        return None
    data = _read_json(persona_dir() / f"{character_id}.persona.json")
    if data and str(data.get("system_prompt") or "").strip():
        return data

    contact = characters.get_character(character_id)
    display_name = name or (contact["name"] if contact else "")
    template = _default_template()
    if not display_name or not template:
        return None
    return {
        "id": character_id,
        "name": display_name,
        "system_prompt": template.replace("{name}", display_name),
        "greeting": "",
    }


def save_persona(character_id: str, name: str, system_prompt: str) -> dict:
    """写入角色卡（含目录创建），返回保存后的内容。"""
    path = persona_dir() / f"{character_id}.persona.json"
    data: dict = _read_json(path) or {}
    data.update(
        {
            "id": character_id,
            "name": name,
            "system_prompt": system_prompt,
            "greeting": data.get("greeting", ""),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data

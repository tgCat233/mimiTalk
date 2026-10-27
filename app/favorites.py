"""收藏联系人：保存在配置文件同目录的 favorites.json。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app import settings


def _path() -> Path:
    return settings.config_path().parent / "favorites.json"


def _read() -> list[str]:
    path = _path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    contacts = data.get("contacts") if isinstance(data, dict) else None
    if not isinstance(contacts, list):
        return []
    return [str(item) for item in contacts]


def favorite_ids() -> set[str]:
    return set(_read())


def set_favorite(contact_id: str, value: bool) -> set[str]:
    contacts = [item for item in _read() if item != contact_id]
    if value:
        contacts.append(contact_id)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
            json.dump({"contacts": contacts}, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return set(contacts)

"""设置读写：config/p3.toml（S1 设置页）。"""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from pathlib import Path

from app.config import BASE_DIR


def config_path() -> Path:
    env = os.environ.get("P3_CONFIG_PATH")
    return Path(env) if env else BASE_DIR / "config" / "p3.toml"


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"不支持的配置类型：{type(value)!r}")


def dump_toml(data: dict) -> str:
    lines: list[str] = ["# 由 P3 设置页写入；可手动编辑。", ""]
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, (dict, list)):
                continue
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
        for key, table in values.items():
            if not isinstance(table, dict):
                continue
            lines.append(f"[{section}.{key}]")
            for sub_key, sub_value in table.items():
                if isinstance(sub_value, (dict, list)):
                    continue
                lines.append(
                    f"{json.dumps(str(sub_key), ensure_ascii=False)} = "
                    f"{_toml_value(sub_value)}"
                )
            lines.append("")
    return "\n".join(lines)


def _read_raw(path: Path) -> dict:
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def public_settings() -> dict:
    """返回可公开的设置（密钥只返回是否已设置）。"""
    data = _read_raw(config_path())
    model = data.get("model", {})
    tts = data.get("tts", {})
    return {
        "model": {
            "base_url": str(model.get("base_url") or ""),
            "model": str(model.get("model") or ""),
            "fake": bool(model.get("fake")),
            "history_limit": int(model.get("history_limit", 30)),
            "has_key": bool(model.get("api_key")),
        },
        "tts": {
            "provider": str(tts.get("provider") or "openai-compatible"),
            "base_url": str(tts.get("base_url") or ""),
            "model": str(tts.get("model") or ""),
            "voice": str(tts.get("voice") or ""),
            "speed": float(tts.get("speed") or 1.0),
            "mode": str(tts.get("mode") or "text"),
            "character_models": {
                str(key): str(value)
                for key, value in (tts.get("character_models") or {}).items()
            },
            "has_key": bool(tts.get("api_key")),
        },
        "log": {"level": str(data.get("log", {}).get("level") or "INFO")},
    }


def update_settings(payload: dict) -> dict:
    """合并写入设置；api_key 为空时保留原值。"""
    path = config_path()
    data = _read_raw(path)

    for section in ("model", "tts"):
        incoming = payload.get(section)
        if not incoming:
            continue
        current = data.setdefault(section, {})
        for key, value in incoming.items():
            if key == "api_key":
                if value:
                    current["api_key"] = value
                continue
            if key == "character_models" and isinstance(value, dict):
                models = current.setdefault("character_models", {})
                for character_id, model in value.items():
                    character_id = str(character_id)
                    model = str(model or "")
                    if model:
                        models[character_id] = model
                    else:
                        models.pop(character_id, None)
                continue
            if value is None:
                continue
            current[key] = value

    _write_atomic(path, dump_toml(data))
    return public_settings()

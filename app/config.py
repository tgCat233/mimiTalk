"""配置加载：内置默认值 + config/p3.toml 覆盖。"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "p3.toml"


HISTORY_LIMIT_MAX = 27100

DEFAULTS: dict = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "log": {"level": "INFO"},
    "storage": {"db_path": ""},
    "model": {
        "base_url": "",
        "api_key": "",
        "model": "",
        "fake": False,
        "history_limit": 30,
    },
    "tts": {
        "provider": "openai-compatible",
        "base_url": "",
        "api_key": "",
        "model": "",
        "voice": "",
        "speed": 1.0,
        "mode": "text",
        "character_models": {},
    },
    "chat": {"recall_reply_chance": 0.3},
}


def _merge(base: dict, override: dict) -> dict:
    """递归合并：override 覆盖 base，缺失项保留默认值。"""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def config_path() -> Path:
    """配置文件路径：环境变量 > 默认 config/p3.toml。"""
    env = os.environ.get("P3_CONFIG_PATH")
    return Path(env) if env else CONFIG_PATH


def load_config(path: Path | None = None) -> dict:
    """读取配置文件；文件不存在时只返回默认值。"""
    target = Path(path) if path is not None else config_path()
    data: dict = {}
    if target.is_file():
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    return _merge(DEFAULTS, data)

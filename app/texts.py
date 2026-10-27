"""界面文案加载：外置 JSON，禁止把用户可见文本写死在代码里。"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEXTS_DIR = BASE_DIR / "config" / "texts"
DEFAULT_LOCALE = "zh-CN"


def load_texts(locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    """读取指定语言的文案表；文件不存在时返回空表。"""
    path = TEXTS_DIR / f"{locale}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"文案表必须是对象：{path}")
    return {str(key): str(value) for key, value in data.items()}

"""SQLite 存储层：会话与消息（S1-B-1）。"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "p3.db"
SCHEMA_VERSION = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'single',
    contact_id TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_message_at INTEGER,
    unread_count INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    settings TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    type TEXT NOT NULL,
    content TEXT,
    asset_id TEXT,
    file_id TEXT,
    width INTEGER,
    height INTEGER,
    status TEXT NOT NULL DEFAULT 'sent',
    reply_to_id TEXT,
    error_text TEXT,
    created_at INTEGER NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}',
    UNIQUE (conversation_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_seq
    ON messages (conversation_id, seq);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_contact
    ON conversations (contact_id) WHERE contact_id IS NOT NULL;
"""


def db_path() -> Path:
    """数据库路径：环境变量 > 配置 > 默认。"""
    env = os.environ.get("P3_DB_PATH")
    if env:
        return Path(env)
    configured = str(load_config().get("storage", {}).get("db_path") or "")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else BASE_DIR / path
    return DEFAULT_DB_PATH


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        conn.executescript(_SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return

    if version == 1:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_contact "
            "ON conversations (contact_id) WHERE contact_id IS NOT NULL"
        )
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        version = 2

    if version == 2:

        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_meta ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_meta (key, value) "
            "VALUES ('initial_seed_done', 'legacy')"
        )
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
        version = 3

    if version != SCHEMA_VERSION:
        raise RuntimeError(f"数据库版本 {version} 与期望 {SCHEMA_VERSION} 不匹配")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """打开连接并确保 schema 已建立。"""
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate(conn)
    return conn


@contextmanager
def session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """连接上下文：退出时关闭。"""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _conversation_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["settings"] = json.loads(data.get("settings") or "{}")
    return data


def _message_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["meta"] = json.loads(data.get("meta") or "{}")
    return data


def create_conversation(
    conn: sqlite3.Connection,
    title: str = "新会话",
    kind: str = "single",
    contact_id: str | None = None,
) -> dict:
    now = _now_ms()
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO conversations
            (id, title, kind, contact_id, created_at, updated_at, settings)
        VALUES (?, ?, ?, ?, ?, ?, '{}')
        """,
        (conversation_id, title, kind, contact_id, now, now),
    )
    conn.commit()
    return get_conversation(conn, conversation_id)


def get_conversation(conn: sqlite3.Connection, conversation_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    return _conversation_dict(row) if row else None


def get_conversation_by_contact(
    conn: sqlite3.Connection, contact_id: str
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM conversations WHERE contact_id = ?", (contact_id,)
    ).fetchone()
    return _conversation_dict(row) if row else None


def list_conversations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.*,
               (SELECT m.content FROM messages m
                WHERE m.conversation_id = c.id AND m.type = 'text' AND m.content IS NOT NULL
                ORDER BY m.seq DESC LIMIT 1) AS last_message
        FROM conversations c
        ORDER BY c.pinned DESC, COALESCE(c.last_message_at, c.updated_at) DESC
        """
    ).fetchall()
    return [_conversation_dict(row) for row in rows]


def add_message(
    conn: sqlite3.Connection,
    conversation_id: str,
    role: str,
    type: str = "text",
    content: str | None = None,
    asset_id: str | None = None,
    file_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    status: str = "sent",
    reply_to_id: str | None = None,
    meta: dict | None = None,
) -> dict:
    if get_conversation(conn, conversation_id) is None:
        raise KeyError(conversation_id)

    now = _now_ms()
    seq = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()[0]
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO messages
            (id, conversation_id, seq, role, type, content, asset_id, file_id,
             width, height, status, reply_to_id, created_at, meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            conversation_id,
            seq,
            role,
            type,
            content,
            asset_id,
            file_id,
            width,
            height,
            status,
            reply_to_id,
            now,
            json.dumps(meta or {}, ensure_ascii=False),
        ),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ?, last_message_at = ? WHERE id = ?",
        (now, now, conversation_id),
    )
    conn.commit()
    return get_message(conn, message_id)


def get_message(conn: sqlite3.Connection, message_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _message_dict(row) if row else None


def update_message(
    conn: sqlite3.Connection,
    message_id: str,
    *,
    type: str | None = None,
    content: str | None = None,
    meta: dict | None = None,
) -> dict | None:
    """更新消息的少量字段；未提供的字段保持原值。"""
    if get_message(conn, message_id) is None:
        return None
    fields: list[str] = []
    values: list = []
    if type is not None:
        fields.append("type = ?")
        values.append(type)
    if content is not None:
        fields.append("content = ?")
        values.append(content)
    if meta is not None:
        fields.append("meta = ?")
        values.append(json.dumps(meta, ensure_ascii=False))
    if fields:
        values.append(message_id)
        conn.execute(f"UPDATE messages SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    return get_message(conn, message_id)


def list_message_ids(conn: sqlite3.Connection, conversation_id: str) -> list[str]:
    """返回会话内全部消息 ID（用于删除时清理附件）。"""
    rows = conn.execute(
        "SELECT id FROM messages WHERE conversation_id = ?", (conversation_id,)
    ).fetchall()
    return [row["id"] for row in rows]


def list_messages(
    conn: sqlite3.Connection,
    conversation_id: str,
    limit: int = 50,
    max_limit: int = 500,
) -> list[dict]:
    """返回最近 limit 条，按 seq 升序排列；max_limit 由调用方控制。"""
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY seq DESC
            LIMIT ?
        ) ORDER BY seq ASC
        """,
        (conversation_id, max(1, min(limit, max_limit))),
    ).fetchall()
    return [_message_dict(row) for row in rows]


def update_conversation_settings(
    conn: sqlite3.Connection, conversation_id: str, settings: dict
) -> dict | None:
    if get_conversation(conn, conversation_id) is None:
        return None
    conn.execute(
        "UPDATE conversations SET settings = ?, updated_at = ? WHERE id = ?",
        (json.dumps(settings, ensure_ascii=False), _now_ms(), conversation_id),
    )
    conn.commit()
    return get_conversation(conn, conversation_id)


def delete_conversation(conn: sqlite3.Connection, conversation_id: str) -> bool:
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    return cursor.rowcount > 0


def delete_message(
    conn: sqlite3.Connection, conversation_id: str, message_id: str
) -> bool:
    row = conn.execute(
        "SELECT id FROM messages WHERE id = ? AND conversation_id = ?",
        (message_id, conversation_id),
    ).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.execute(
        "UPDATE conversations SET last_message_at = "
        "(SELECT MAX(created_at) FROM messages WHERE conversation_id = ?), "
        "updated_at = ? WHERE id = ?",
        (conversation_id, _now_ms(), conversation_id),
    )
    conn.commit()
    return True


def mark_quote_deleted(
    conn: sqlite3.Connection, conversation_id: str, message_id: str
) -> int:
    """把后续消息里对被删/撤回消息的引用标记为已删除，并移除引用原文。"""
    rows = conn.execute(
        "SELECT id, meta FROM messages WHERE conversation_id = ? AND meta LIKE ?",
        (conversation_id, f'%"{message_id}"%'),
    ).fetchall()
    changed = 0
    for row in rows:
        meta = _message_dict(row)["meta"]
        quote = meta.get("quote")
        if not isinstance(quote, dict) or str(quote.get("id")) != str(message_id):
            continue
        if quote.get("deleted"):
            continue
        quote["deleted"] = True
        quote.pop("text", None)
        meta["quote"] = quote
        conn.execute(
            "UPDATE messages SET meta = ? WHERE id = ?",
            (json.dumps(meta, ensure_ascii=False), row["id"]),
        )
        changed += 1
    if changed:
        conn.commit()
    return changed


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def seed_initial_conversations(
    conn: sqlite3.Connection, contacts: list[dict]
) -> int:
    """首次启动预建初始会话；之后即使全部删除也不再补建。"""
    if get_meta(conn, "initial_seed_done") is not None:
        return 0
    created = 0
    if not list_conversations(conn):

        for contact in reversed(contacts):
            create_conversation(
                conn,
                title=contact["name"],
                kind="single",
                contact_id=contact["id"],
            )
            created += 1
    set_meta(conn, "initial_seed_done", str(_now_ms()))
    return created

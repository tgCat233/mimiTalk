"""图片上传与读取（S1-C-1）。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import BASE_DIR

router = APIRouter(prefix="/api")

MAX_BYTES = 32 * 1024 * 1024
ALLOWED = {"image/png": ".png", "image/jpeg": ".jpg"}


def upload_dir() -> Path:
    """上传目录：环境变量 > 默认 data/uploads。"""
    env = os.environ.get("P3_UPLOAD_DIR")
    return Path(env) if env else BASE_DIR / "data" / "uploads"


@router.post("/uploads", status_code=201)
async def upload(file: UploadFile = File(...)) -> dict:
    """接收 PNG / JPEG（≤8 MB），落盘并返回 file_id。"""
    ext = ALLOWED.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 PNG / JPEG")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 32 MB")
    target_dir = upload_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    file_id = f"{uuid.uuid4().hex}{ext}"
    (target_dir / file_id).write_bytes(data)
    return {"file_id": file_id, "url": f"/api/uploads/{file_id}", "size": len(data)}


@router.get("/uploads/{file_id}")
def get_upload(file_id: str) -> FileResponse:
    root = upload_dir().resolve()
    target = (root / file_id).resolve()
    if target.parent != root or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(target)


@router.delete("/uploads/{file_id}", status_code=204)
def delete_upload(file_id: str) -> None:
    root = upload_dir().resolve()
    target = (root / file_id).resolve()
    if target.parent != root or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    target.unlink()

"""P3 后端入口：健康检查、文案接口与静态前端托管（S0 骨架）。"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import characters, chat, conversations, db, settings_api, tts_api, uploads
from app.config import load_config
from app.logging import setup_logging
from app.texts import load_texts

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "0.1.2"

config = load_config()
setup_logging(config.get("log", {}).get("level", "INFO"))
logger = logging.getLogger("p3")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("P3 后端启动，version=%s", VERSION)
    if not os.environ.get("P3_DISABLE_SEED"):
        with db.session() as conn:
            created = db.seed_initial_conversations(conn, characters.initial_contacts())
        if created:
            logger.info("首次启动：已创建 %d 个初始会话", created)
    yield
    logger.info("P3 后端停止")


app = FastAPI(
    title="P3",
    version=VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.include_router(conversations.router)
app.include_router(uploads.router)
app.include_router(chat.router)
app.include_router(tts_api.router)
app.include_router(settings_api.router)

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")

_DOCS_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P3 API</title>
  <link rel="stylesheet" href="/static/swagger/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="/static/swagger/swagger-ui-bundle.js"></script>
  <script src="/static/swagger/swagger-ui-standalone-preset.js"></script>
  <script>
    window.ui = SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
      layout: 'BaseLayout',
      deepLinking: true,
    })
  </script>
</body>
</html>
"""


@app.get("/docs", include_in_schema=False)
def docs() -> HTMLResponse:
    """接口文档：Swagger UI 资源本地自托管，不依赖外网 CDN。"""
    return HTMLResponse(_DOCS_HTML)


@app.get("/api/health")
def health() -> dict:
    """健康检查：确认服务与配置加载正常。"""
    return {
        "status": "ok",
        "version": VERSION,
        "config_loaded": bool(config),
    }


@app.get("/api/texts")
def texts() -> dict[str, str]:
    """返回界面文案表（外置，可在 config/texts/ 中修改）。"""
    return load_texts()



_dist = BASE_DIR / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")

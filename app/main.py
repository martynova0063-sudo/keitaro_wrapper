from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — регистрируем модели
from app.database import Base, engine
from app.routers import campaigns, editor

app = FastAPI(title="Keitaro Wrapper", version="1.0.0")

app.include_router(campaigns.router)
app.include_router(editor.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def create_tables_fallback():
    """Страховка, если забыли запустить миграции: create_all не удаляет данные."""
    Base.metadata.create_all(bind=engine)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

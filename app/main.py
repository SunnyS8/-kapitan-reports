from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

from app.config import BASE_DIR, REPORTS_DIR, UPLOADS_DIR
from app.routers import pages, api, upload

app = FastAPI(title="Kapitan Reports", version="1.0.0")

static_dir = BASE_DIR / "app" / "static"
templates_dir = BASE_DIR / "app" / "templates"
uploads_dir = UPLOADS_DIR
reports_dir = REPORTS_DIR

for d in [static_dir, templates_dir, uploads_dir, reports_dir]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
app.include_router(upload.router, prefix="/upload")

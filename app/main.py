from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.routers import pages, api, upload

app = FastAPI(title="Kapitan Reports", version="1.0.0")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")
app.include_router(upload.router, prefix="/upload")

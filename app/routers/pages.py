from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import REPORT_TYPES, UPLOADS_DIR, REPORTS_DIR, BASE_DIR

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    reports = [{"key": k, "name": v} for k, v in REPORT_TYPES.items()]
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "reports": reports,
    })


@router.get("/report/{report_type}", response_class=HTMLResponse)
async def report_page(request: Request, report_type: str):
    title = REPORT_TYPES.get(report_type, "Неизвестный отчёт")
    return templates.TemplateResponse(f"{report_type}.html", {
        "request": request,
        "report_type": report_type,
        "title": title,
    })

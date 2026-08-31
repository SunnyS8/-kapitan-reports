from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import REPORT_TYPES, BASE_DIR

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    reports = [{"key": k, "name": v} for k, v in REPORT_TYPES.items()]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"reports": reports},
    )


@router.get("/report/{report_type}", response_class=HTMLResponse)
async def report_page(request: Request, report_type: str):
    title = REPORT_TYPES.get(report_type, "Неизвестный отчёт")
    return templates.TemplateResponse(
        request=request,
        name=f"{report_type}.html",
        context={"report_type": report_type, "title": title},
    )

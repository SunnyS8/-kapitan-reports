from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import shutil
import uuid
import asyncio

from app.config import UPLOADS_DIR, REPORTS_DIR, INBOX_DIR, REPORT_OUT_DIRS, MONTHLY_REPORTS, KNOWLEDGE_ANALYTICS
from app.services.report_sales import generate_sales_clients
from app.services.report_products import generate_sales_products
from app.services.report_inventory import generate_inventory
from app.services.report_dynamics import generate_dynamics
from app.services.report_forecast import generate_forecast
from app.services.report_debt import generate_debt
from app.services.report_debt_manager import generate_debt_manager
from app.services.report_stock_dynamics import generate_stock_dynamics
from app.services.report_edo import generate_edo
from app.services.report_clients import generate_clients
from app.services.report_nelikvid import generate_nelikvid
from app.services.report_top import generate_top_clients, generate_top_products
from app.services.excel_export import export_to_excel, export_multi_sheet, save_report_to_knowledge
from app.services.note_builder import auto_note, save_note_to_knowledge
import app.config as app_config

router = APIRouter()

GENERATORS = {
    "sales_clients": lambda fs, dt=None, du=None: generate_sales_clients(fs, dt, du),
    "sales_products": lambda fs, dt=None, du=None: generate_sales_products(fs, dt, du),
    "inventory": lambda fs, dt=None, du=None: generate_inventory(fs, dt, du),
    "dynamics": lambda fs, dt=None, du=None: generate_dynamics(fs, dt, du),
    "forecast": lambda fs, dt=None, du=None: generate_forecast(fs, dt, du),
    "debt": lambda fs, dt=None, du=None: generate_debt(fs, dt, du),
    "debt_manager": lambda fs, dt=None, du=None: generate_debt_manager(fs, dt, du),
    "stock_dynamics": lambda fs, dt=None, du=None: generate_stock_dynamics(fs, dt, du),
    "edo": lambda fs, dt=None, du=None: generate_edo(fs, dt, du),
    "clients": lambda fs, dt=None, du=None: generate_clients(fs, dt, du),
    "nelikvid": lambda fs, dt=None, du=None: generate_nelikvid(fs, dt, du),
    "top_clients": lambda fs, dt=None, du=None: generate_top_clients(fs, dt, du),
    "top_products": lambda fs, dt=None, du=None: generate_top_products(fs, dt, du),
}


def _filter_by_date(df: pd.DataFrame, date_from: Optional[str], date_to: Optional[str]) -> pd.DataFrame:
    """Фильтрует DataFrame по колонке 'date'."""
    if "date" not in df.columns:
        return df
    if date_from:
        try:
            d_from = pd.to_datetime(date_from, errors="coerce")
            if pd.notna(d_from):
                df = df[df["date"] >= d_from]
        except Exception:
            pass
    if date_to:
        try:
            d_to = pd.to_datetime(date_to, errors="coerce") + pd.Timedelta(days=1)
            if pd.notna(d_to):
                df = df[df["date"] < d_to]
        except Exception:
            pass
    return df


class GenerateRequest(BaseModel):
    files: Optional[list[str]] = None  # имена файлов в INBOX_DIR
    date_from: Optional[str] = None     # дата начала (YYYY-MM-DD)
    date_to: Optional[str] = None       # дата окончания (YYYY-MM-DD)


class AnalyzeRequest(BaseModel):
    files: Optional[list[str]] = None  # имена файлов в INBOX_DIR
    ai: bool = False                   # True — «от аналитика» через Hermes
    date_from: Optional[str] = None
    date_to: Optional[str] = None


def _resolve_input_files(selected: Optional[list[str]]) -> list[Path]:
    """Собирает файлы для генерации: из выбранных в INBOX или все из INBOX."""
    if selected:
        resolved = []
        for name in selected:
            p = (INBOX_DIR / name).resolve()
            if (p.is_relative_to(INBOX_DIR.resolve()) and p.exists() and p.is_file()
                    and p.suffix.lower() in (".xlsx", ".xls")):
                resolved.append(p)
        if resolved:
            return resolved

    files = sorted(INBOX_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    xlsx_files = [f for f in files if f.suffix.lower() in (".xlsx", ".xls")]
    return xlsx_files


@router.get("/inbox/files")
async def inbox_files():
    files = []
    folders = []
    for entry in sorted(INBOX_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if entry.is_dir():
            folders.append({
                "name": entry.name,
                "path": str(entry.relative_to(INBOX_DIR)),
            })
        elif entry.is_file() and entry.suffix.lower() in (".xlsx", ".xls"):
            files.append({
                "name": entry.name,
                "size": entry.stat().st_size,
                "modified": int(entry.stat().st_mtime),
            })
    return {"files": files, "folders": folders, "dir": str(INBOX_DIR)}


@router.get("/inbox/folder/{folder_path:path}")
async def inbox_folder_files(folder_path: str):
    """Возвращает файлы из конкретной подпапки inbox."""
    target = INBOX_DIR / folder_path
    if not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Папка не найдена: {folder_path}")
    files = []
    for entry in sorted(target.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if entry.is_file() and entry.suffix.lower() in (".xlsx", ".xls"):
            files.append({
                "name": entry.name,
                "path": str(entry.relative_to(INBOX_DIR)),
                "size": entry.stat().st_size,
                "modified": int(entry.stat().st_mtime),
            })
    return {"files": files, "folder": folder_path}


@router.post("/generate/{report_type}")
async def generate_report(report_type: str, req: Optional[GenerateRequest] = None):
    if report_type not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип отчёта: {report_type}")

    selected = req.files if req else None
    xlsx_files = _resolve_input_files(selected)
    date_from = req.date_from if req else None
    date_to = req.date_to if req else None

    if not xlsx_files:
        raise HTTPException(status_code=400, detail="Нет файлов выгрузок. Положите выгрузки в папку Входные_выгрузки.")

    try:
        result = GENERATORS[report_type](xlsx_files, date_from, date_to)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {e}")

    # Экспорт в Excel
    data = result.get("data", [])
    internal = result.get("internal") or []
    warehouses = result.get("warehouses") or []
    filename = ""
    if data or internal:
        if report_type == "nelikvid":
            sheets = {
                "Сводная": data[:10],
                "Товары": data,
            }
            filename = export_multi_sheet(sheets, report_type, REPORTS_DIR)
        else:
            extra = {}
            if internal:
                extra["Внутренние (НДС)"] = internal
            if warehouses:
                extra["Сводка по складам"] = warehouses
            filename = export_to_excel(data, report_type, REPORTS_DIR, extra_sheets=extra if extra else None)

    # Запись в папки базы знаний (xlsx + md + месячные)
    try:
        save_report_to_knowledge(report_type, data, result.get("summary", {}), filename, app_config,
                                 internal=internal if internal else None)
    except Exception as e:
        # Не роняем отчёт из-за проблем с записью в базу знаний
        pass

    return {
        "report_type": report_type,
        "summary": result.get("summary", {}),
        "data": data,
        "chart": result.get("chart", result.get("chart_category", {})),
        "chart_warehouse": result.get("chart_warehouse"),
        "warehouses": warehouses,
        "by_warehouse": result.get("by_warehouse") or [],
        "internal": internal,
        "filename": filename,
    }


@router.get("/download/{filename}")
async def download_report(filename: str):
    path = REPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _search_knowledge_file(filename: str):
    """Ищет файл в подпапках базы знаний 06 - Аналитика и отчёты."""
    if not KNOWLEDGE_ANALYTICS.is_dir():
        return None
    for d in KNOWLEDGE_ANALYTICS.iterdir():
        if d.is_dir():
            cand = d / filename
            if cand.exists():
                return cand
    return None


@router.get("/note_file/{filename}")
async def download_note_file(filename: str):
    path = _search_knowledge_file(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Записка не найдена")
    return FileResponse(path, filename=filename,
                        media_type="text/markdown; charset=utf-8")


@router.post("/analyze/{report_type}")
async def analyze_report(report_type: str, req: Optional[AnalyzeRequest] = None):
    """Аналитическая записка к отчёту.

    mode=auto (по умолчанию): быстрый разбор по правилам.
    mode=ai:                    генерация через Hermes-аналитика (профиль analyst).
    В обоих случаях .md-файл сохраняется в папку отчёта в базе знаний.
    """
    if report_type not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип отчёта: {report_type}")

    selected = req.files if req else None
    ai_mode = bool(req.ai) if req else False
    date_from = req.date_from if req else None
    date_to = req.date_to if req else None
    xlsx_files = _resolve_input_files(selected)

    if not xlsx_files:
        raise HTTPException(status_code=400, detail="Нет файлов выгрузок. Положите выгрузки в папку Входные_выгрузки.")

    try:
        result = GENERATORS[report_type](xlsx_files, date_from, date_to)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчёта: {e}")

    summary = result.get("summary", {})

    if ai_mode:
        try:
            from app.services.openrouter_note import build_ai_note, note_to_markdown
            ai_text = await asyncio.to_thread(build_ai_note, report_type, result)
            note_text = note_to_markdown(report_type, ai_text)
            mode = "ai"
        except Exception as e:
            note_text = (
                "# Аналитическая записка\n\n"
                f"**Не удалось получить записку от аналитика:** {e}\n\n"
                "Используйте режим «Авто» для быстрого разбора.\n"
            )
            mode = "ai_error"
    else:
        note_text = auto_note(report_type, result)
        mode = "auto"

    filename = save_note_to_knowledge(report_type, note_text, app_config)

    return {
        "report_type": report_type,
        "mode": mode,
        "note": note_text,
        "filename": filename or None,
        "summary": summary,
    }

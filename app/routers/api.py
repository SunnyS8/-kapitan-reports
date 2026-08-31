from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import shutil
import uuid

from app.config import UPLOADS_DIR, REPORTS_DIR
from app.services.report_sales import generate_sales_clients
from app.services.report_products import generate_sales_products
from app.services.report_inventory import generate_inventory
from app.services.report_dynamics import generate_dynamics
from app.services.report_forecast import generate_forecast
from app.services.report_debt import generate_debt
from app.services.report_nelikvid import generate_nelikvid
from app.services.excel_export import export_to_excel, export_multi_sheet

router = APIRouter()

GENERATORS = {
    "sales_clients": lambda fs: generate_sales_clients(fs),
    "sales_products": lambda fs: generate_sales_products(fs),
    "inventory": lambda fs: generate_inventory(fs),
    "dynamics": lambda fs: generate_dynamics(fs),
    "forecast": lambda fs: generate_forecast(fs),
    "debt": lambda fs: generate_debt(fs),
    "nelikvid": lambda fs: generate_nelikvid(fs),
}


@router.post("/generate/{report_type}")
async def generate_report(report_type: str):
    if report_type not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип отчёта: {report_type}")

    # Берём последние загруженные файлы
    files = sorted(UPLOADS_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    xlsx_files = [f for f in files if f.suffix in (".xlsx", ".xls")]

    if not xlsx_files:
        raise HTTPException(status_code=400, detail="Нет загруженных файлов. Сначала загрузите файлы.")

    try:
        result = GENERATORS[report_type](xlsx_files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {e}")

    # Экспорт в Excel
    data = result.get("data", [])
    filename = ""
    if data:
        if report_type == "nelikvid":
            sheets = {
                "Сводная": data[:10],
                "Товары": data,
            }
            filename = export_multi_sheet(sheets, report_type, REPORTS_DIR)
        else:
            filename = export_to_excel(data, report_type, REPORTS_DIR)

    return {
        "report_type": report_type,
        "summary": result.get("summary", {}),
        "data": data,
        "chart": result.get("chart", result.get("chart_category", {})),
        "chart_warehouse": result.get("chart_warehouse"),
        "filename": filename,
    }


@router.get("/download/{filename}")
async def download_report(filename: str):
    path = REPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=filename,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
